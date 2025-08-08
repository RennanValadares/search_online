import asyncio
import time
from typing import List, Dict, Any, Optional

from app.domain.contracts import SearchProvider, Crawler, LLMClient, CacheProvider
from app.domain.models import LLMMessage, QAResponse, QASource, SearchProvider as SearchProviderEnum
from app.core.errors import SearchAPIError
from app.core.logger import get_logger
from app.services.search_service import SearchService
from app.services.crawl_service import CrawlService

logger = get_logger(__name__)


class QAService:
    """Service for complete search-read-answer pipeline"""
    
    def __init__(
        self,
        search_service: SearchService,
        crawl_service: CrawlService,
        llm_client: LLMClient,
        cache: Optional[CacheProvider] = None
    ):
        self.search_service = search_service
        self.crawl_service = crawl_service
        self.llm_client = llm_client
        self.cache = cache
    
    async def search_read_answer(
        self,
        query: str,
        search_providers: List[str] = None,
        num_search_results: int = 8,
        max_docs_to_crawl: int = 5,
        model: Optional[str] = None,
        render_js: bool = False,
        return_citations: bool = True,
        include_debug: bool = False,
        **kwargs
    ) -> QAResponse:
        """Complete pipeline: search -> crawl -> answer with LLM"""
        
        start_time = time.time()
        intermediate_steps = {} if include_debug else None
        
        try:
            # Step 1: Search
            logger.info("Starting search phase", query=query)
            search_start = time.time()
            
            search_results = await self.search_service.search(
                query=query,
                providers=search_providers or ["google", "bing"],
                num=num_search_results,
                **kwargs
            )
            
            search_time = time.time() - search_start
            if intermediate_steps is not None:
                intermediate_steps["search"] = {
                    "time": search_time,
                    "results_count": len(search_results),
                    "providers": search_providers
                }
            
            if not search_results:
                raise SearchAPIError("No search results found")
            
            # Step 2: Select top URLs to crawl
            urls_to_crawl = [str(result.url) for result in search_results[:max_docs_to_crawl]]
            
            logger.info("Starting crawl phase", urls_count=len(urls_to_crawl))
            crawl_start = time.time()
            
            # Step 3: Crawl and extract content
            crawl_results = await self.crawl_service.crawl_urls(
                urls=urls_to_crawl,
                render_js=render_js,
                max_concurrent=3
            )
            
            crawl_time = time.time() - crawl_start
            if intermediate_steps is not None:
                intermediate_steps["crawl"] = {
                    "time": crawl_time,
                    "urls_attempted": len(urls_to_crawl),
                    "successful_crawls": len([r for r in crawl_results if r["status"] == "success"])
                }
            
            # Step 4: Filter successful crawls and prepare sources
            successful_crawls = [
                result for result in crawl_results 
                if result["status"] == "success" and result["text"].strip()
            ]
            
            if not successful_crawls:
                raise SearchAPIError("No content could be extracted from search results")
            
            # Step 5: Prepare context for LLM
            sources = []
            context_parts = []
            
            for i, crawl_result in enumerate(successful_crawls):
                # Find corresponding search result for metadata
                search_result = next(
                    (sr for sr in search_results if str(sr.url) == crawl_result["url"]),
                    None
                )
                
                source = QASource(
                    id=i + 1,
                    title=crawl_result["title"] or (search_result.title if search_result else "Untitled"),
                    url=crawl_result["url"],
                    snippet=search_result.snippet if search_result else None,
                    provider=search_result.provider if search_result else SearchProviderEnum.GOOGLE
                )
                sources.append(source)
                
                # Truncate content to avoid token limits
                content = crawl_result["text"][:2000]  # Rough token limit
                context_parts.append(f"[{i + 1}] {source.title}\nURL: {source.url}\nContent: {content}")
            
            # Step 6: Generate answer with LLM
            logger.info("Starting LLM phase", sources_count=len(sources))
            llm_start = time.time()
            
            context = "\n\n".join(context_parts)
            
            messages = [
                LLMMessage(
                    role="system",
                    content=(
                        "You are a helpful research assistant. Answer the user's question based on the provided sources. "
                        "Always cite your sources using [number] format. Be concise but comprehensive. "
                        "If the sources don't contain enough information to answer the question, say so clearly."
                    )
                ),
                LLMMessage(
                    role="user",
                    content=f"Question: {query}\n\nSources:\n{context}\n\nPlease provide a comprehensive answer with citations."
                )
            ]
            
            llm_response = await self.llm_client.complete(
                messages=messages,
                model=model,
                temperature=0.1,
                max_tokens=1000
            )
            
            llm_time = time.time() - llm_start
            if intermediate_steps is not None:
                intermediate_steps["llm"] = {
                    "time": llm_time,
                    "model": llm_response.model,
                    "tokens_used": llm_response.tokens_used,
                    "finish_reason": llm_response.finish_reason
                }
            
            # Step 7: Prepare response
            total_time = time.time() - start_time
            
            response = QAResponse(
                answer=llm_response.content,
                sources=sources if return_citations else [],
                query=query,
                tokens_used=llm_response.tokens_used,
                processing_time=total_time,
                intermediate_steps=intermediate_steps
            )
            
            logger.info("QA pipeline completed", 
                       query=query,
                       total_time=total_time,
                       sources_count=len(sources),
                       tokens_used=llm_response.tokens_used)
            
            return response
            
        except Exception as e:
            logger.error("QA pipeline failed", query=query, error=str(e))
            raise SearchAPIError(f"QA pipeline failed: {str(e)}")
    
    async def summarize_content(
        self,
        text: Optional[str] = None,
        url: Optional[str] = None,
        model: Optional[str] = None,
        max_length: int = 200,
        **kwargs
    ) -> Dict[str, Any]:
        """Summarize text content or content from URL"""
        
        if not text and not url:
            raise SearchAPIError("Either text or url must be provided")
        
        # If URL provided, extract content first
        if url and not text:
            logger.info("Extracting content from URL for summarization", url=url)
            content = await self.crawl_service.extract_content(url)
            text = content.text
        
        if not text or not text.strip():
            raise SearchAPIError("No content to summarize")
        
        # Truncate if too long
        if len(text) > 8000:  # Rough token limit
            text = text[:8000] + "..."
        
        # Generate summary
        messages = [
            LLMMessage(
                role="system",
                content=f"Summarize the following text in approximately {max_length} words. Be concise and capture the key points."
            ),
            LLMMessage(
                role="user",
                content=text
            )
        ]
        
        response = await self.llm_client.complete(
            messages=messages,
            model=model,
            temperature=0.1,
            max_tokens=max_length * 2  # Rough conversion
        )
        
        return {
            "summary": response.content,
            "original_length": len(text.split()),
            "summary_length": len(response.content.split()),
            "tokens_used": response.tokens_used,
            "model": response.model
        }