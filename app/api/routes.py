import time
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional

from app.api.models import (
    SearchRequest, SearchResponse, SearchResultResponse,
    CrawlRequest, CrawlResponse, CrawlResultResponse,
    SummarizeRequest, SummarizeResponse,
    QARequest, QAResponse, QASourceResponse,
    SearchProvidersEnum, ErrorResponse
)
from app.core.errors import SearchAPIError, SearchProviderError, CrawlerError, LLMError
from app.core.logger import get_logger
from app.services.search_service import SearchService
from app.services.crawl_service import CrawlService
from app.services.qa_service import QAService

logger = get_logger(__name__)
router = APIRouter()


# Dependency injection placeholders - these will be set in main.py
search_service: Optional[SearchService] = None
crawl_service: Optional[CrawlService] = None
qa_service: Optional[QAService] = None


def get_search_service() -> SearchService:
    if search_service is None:
        raise HTTPException(status_code=500, detail="Search service not initialized")
    return search_service


def get_crawl_service() -> CrawlService:
    if crawl_service is None:
        raise HTTPException(status_code=500, detail="Crawl service not initialized")
    return crawl_service


def get_qa_service() -> QAService:
    if qa_service is None:
        raise HTTPException(status_code=500, detail="QA service not initialized")
    return qa_service


@router.get("/v1/search", response_model=SearchResponse)
async def search_endpoint(
    q: str = Query(..., description="Search query"),
    providers: List[SearchProvidersEnum] = Query(default=[SearchProvidersEnum.GOOGLE], description="Search providers"),
    num: int = Query(default=10, ge=1, le=50, description="Number of results"),
    lang: Optional[str] = Query(None, description="Language code"),
    country: Optional[str] = Query(None, description="Country code"),
    service: SearchService = Depends(get_search_service)
):
    """Search across multiple providers"""
    
    start_time = time.time()
    
    try:
        logger.info("Search request", query=q, providers=providers, num=num)
        
        # Convert enum to string
        provider_names = [p.value for p in providers]
        
        results = await service.search(
            query=q,
            providers=provider_names,
            num=num,
            lang=lang,
            country=country
        )
        
        # Convert to response format
        response_results = [
            SearchResultResponse(
                title=result.title,
                url=result.url,
                snippet=result.snippet,
                provider=SearchProvidersEnum(result.provider.value),
                rank=result.rank,
                metadata=result.metadata
            )
            for result in results
        ]
        
        processing_time = time.time() - start_time
        
        return SearchResponse(
            results=response_results,
            query=q,
            total_results=len(response_results),
            providers_used=providers,
            processing_time=processing_time
        )
        
    except SearchProviderError as e:
        logger.error("Search provider error", error=str(e))
        raise HTTPException(status_code=502, detail=f"Search provider error: {str(e)}")
    except Exception as e:
        logger.error("Search error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/v1/crawl", response_model=CrawlResponse)
async def crawl_endpoint(
    request: CrawlRequest,
    service: CrawlService = Depends(get_crawl_service)
):
    """Crawl and extract content from URLs"""
    
    start_time = time.time()
    
    try:
        logger.info("Crawl request", urls_count=len(request.urls), render_js=request.render_js)
        
        # Convert URLs to strings
        urls = [str(url) for url in request.urls]
        
        results = await service.crawl_urls(
            urls=urls,
            render_js=request.render_js,
            max_concurrent=request.max_concurrent
        )
        
        # Convert to response format
        response_results = [
            CrawlResultResponse(
                url=result["url"],
                status=result["status"],
                text=result["text"],
                title=result["title"],
                word_count=result["word_count"],
                language=result.get("language"),
                author=result.get("author"),
                publish_date=result.get("publish_date"),
                error=result.get("error"),
                metadata=result.get("metadata", {})
            )
            for result in results
        ]
        
        processing_time = time.time() - start_time
        successful_crawls = len([r for r in results if r["status"] == "success"])
        
        return CrawlResponse(
            results=response_results,
            total_urls=len(request.urls),
            successful_crawls=successful_crawls,
            processing_time=processing_time
        )
        
    except CrawlerError as e:
        logger.error("Crawler error", error=str(e))
        raise HTTPException(status_code=502, detail=f"Crawler error: {str(e)}")
    except Exception as e:
        logger.error("Crawl error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Crawl failed: {str(e)}")


@router.post("/v1/summarize", response_model=SummarizeResponse)
async def summarize_endpoint(
    request: SummarizeRequest,
    service: QAService = Depends(get_qa_service)
):
    """Summarize text or content from URL"""
    
    start_time = time.time()
    
    try:
        logger.info("Summarize request", has_text=bool(request.text), has_url=bool(request.url))
        
        if not request.text and not request.url:
            raise HTTPException(status_code=400, detail="Either text or url must be provided")
        
        result = await service.summarize_content(
            text=request.text,
            url=str(request.url) if request.url else None,
            model=request.model,
            max_length=request.max_length
        )
        
        processing_time = time.time() - start_time
        
        return SummarizeResponse(
            summary=result["summary"],
            original_length=result["original_length"],
            summary_length=result["summary_length"],
            tokens_used=result["tokens_used"],
            model=result["model"],
            processing_time=processing_time
        )
        
    except LLMError as e:
        logger.error("LLM error", error=str(e))
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")
    except Exception as e:
        logger.error("Summarize error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")


@router.post("/v1/qa/search-read", response_model=QAResponse)
async def qa_search_read_endpoint(
    request: QARequest,
    service: QAService = Depends(get_qa_service)
):
    """Complete search-read-answer pipeline"""
    
    try:
        logger.info("QA request", query=request.query, providers=request.search_providers)
        
        # Convert enum to string
        provider_names = [p.value for p in request.search_providers]
        
        result = await service.search_read_answer(
            query=request.query,
            search_providers=provider_names,
            num_search_results=request.num_search_results,
            max_docs_to_crawl=request.max_docs_to_crawl,
            model=request.model,
            render_js=request.render_js,
            return_citations=request.return_citations,
            include_debug=request.include_debug
        )
        
        # Convert to response format
        response_sources = [
            QASourceResponse(
                id=source.id,
                title=source.title,
                url=source.url,
                snippet=source.snippet,
                provider=SearchProvidersEnum(source.provider.value)
            )
            for source in result.sources
        ]
        
        return QAResponse(
            answer=result.answer,
            sources=response_sources,
            query=result.query,
            tokens_used=result.tokens_used,
            processing_time=result.processing_time,
            intermediate_steps=result.intermediate_steps
        )
        
    except SearchAPIError as e:
        logger.error("QA pipeline error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("QA error", error=str(e))
        raise HTTPException(status_code=500, detail=f"QA pipeline failed: {str(e)}")


@router.get("/v1/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}