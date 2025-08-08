import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import configure_logging, get_logger
from app.core.errors import SearchAPIError, SearchProviderError, CrawlerError, LLMError

# Import providers
from app.providers.search.google import GoogleSearchProvider
from app.providers.search.bing import BingSearchProvider
from app.providers.crawl.http_crawler import HttpCrawler
from app.providers.crawl.playwright_crawler import PlaywrightCrawler
from app.providers.llm.openai_client import OpenAIClient
from app.providers.llm.openrouter_client import OpenRouterClient

# Import services
from app.services.search_service import SearchService
from app.services.crawl_service import CrawlService
from app.services.qa_service import QAService

# Import cache
from app.utils.cache import RedisCache, MemoryCache

# Import API routes
from app.api import routes

# Configure logging
configure_logging(debug=settings.debug)
logger = get_logger(__name__)

# Global variables for services
http_client: httpx.AsyncClient = None
cache_provider = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global http_client, cache_provider
    
    logger.info("Starting SearchAPI application")
    
    # Initialize HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.http_timeout),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
    )
    
    # Initialize cache
    if settings.redis_url:
        cache_provider = RedisCache(settings.redis_url)
        await cache_provider.connect()
    else:
        logger.warning("Redis not configured, using memory cache")
        cache_provider = MemoryCache()
    
    # Initialize search providers
    search_providers = {}
    
    if settings.google_api_key and settings.google_cx:
        search_providers["google"] = GoogleSearchProvider(
            api_key=settings.google_api_key,
            cx=settings.google_cx,
            client=http_client
        )
        logger.info("Google search provider initialized")
    
    if settings.bing_api_key:
        search_providers["bing"] = BingSearchProvider(
            api_key=settings.bing_api_key,
            client=http_client
        )
        logger.info("Bing search provider initialized")
    
    if not search_providers:
        logger.warning("No search providers configured")
    
    # Initialize crawlers
    http_crawler = HttpCrawler(http_client)
    playwright_crawler = None  # Will be initialized on demand
    
    # Initialize LLM clients
    llm_client = None
    if settings.openai_api_key:
        llm_client = OpenAIClient(api_key=settings.openai_api_key)
        logger.info("OpenAI client initialized")
    elif settings.openrouter_api_key:
        llm_client = OpenRouterClient(api_key=settings.openrouter_api_key)
        logger.info("OpenRouter client initialized")
    else:
        logger.warning("No LLM client configured")
    
    # Initialize services
    search_service = SearchService(
        providers=search_providers,
        cache=cache_provider
    )
    
    crawl_service = CrawlService(
        http_crawler=http_crawler,
        js_crawler=playwright_crawler,
        cache=cache_provider
    )
    
    qa_service = QAService(
        search_service=search_service,
        crawl_service=crawl_service,
        llm_client=llm_client,
        cache=cache_provider
    ) if llm_client else None
    
    # Set services in routes module
    routes.search_service = search_service
    routes.crawl_service = crawl_service
    routes.qa_service = qa_service
    
    logger.info("SearchAPI application started successfully")
    
    yield
    
    # Cleanup
    logger.info("Shutting down SearchAPI application")
    
    if http_client:
        await http_client.aclose()
    
    if cache_provider and hasattr(cache_provider, 'disconnect'):
        await cache_provider.disconnect()
    
    logger.info("SearchAPI application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="SearchAPI",
    description="Modular Search + Scraping + LLM API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(routes.router)

# Global exception handlers
@app.exception_handler(SearchProviderError)
async def search_provider_error_handler(request, exc: SearchProviderError):
    logger.error("Search provider error", error=str(exc), details=exc.details)
    return JSONResponse(
        status_code=502,
        content={"error": "Search provider error", "detail": str(exc)}
    )

@app.exception_handler(CrawlerError)
async def crawler_error_handler(request, exc: CrawlerError):
    logger.error("Crawler error", error=str(exc), details=exc.details)
    return JSONResponse(
        status_code=502,
        content={"error": "Crawler error", "detail": str(exc)}
    )

@app.exception_handler(LLMError)
async def llm_error_handler(request, exc: LLMError):
    logger.error("LLM error", error=str(exc), details=exc.details)
    return JSONResponse(
        status_code=502,
        content={"error": "LLM error", "detail": str(exc)}
    )

@app.exception_handler(SearchAPIError)
async def search_api_error_handler(request, exc: SearchAPIError):
    logger.error("SearchAPI error", error=str(exc), details=exc.details)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal error", "detail": str(exc)}
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "SearchAPI - Modular Search + Scraping + LLM",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/v1/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )