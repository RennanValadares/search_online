import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from app.domain.contracts import Crawler, CacheProvider
from app.domain.models import ExtractedContent, Page
from app.core.errors import CrawlerError
from app.core.logger import get_logger

logger = get_logger(__name__)


class CrawlService:
    """Service for crawling and extracting content from URLs"""
    
    def __init__(
        self, 
        http_crawler: Crawler,
        js_crawler: Optional[Crawler] = None,
        cache: Optional[CacheProvider] = None
    ):
        self.http_crawler = http_crawler
        self.js_crawler = js_crawler
        self.cache = cache
    
    async def crawl_urls(
        self, 
        urls: List[str], 
        render_js: bool = False,
        max_concurrent: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Crawl multiple URLs and extract content"""
        
        # Limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def crawl_single(url: str) -> Dict[str, Any]:
            async with semaphore:
                return await self._crawl_single_url(url, render_js, **kwargs)
        
        # Execute crawls in parallel
        tasks = [crawl_single(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            url = urls[i]
            
            if isinstance(result, Exception):
                logger.error("Crawl failed", url=url, error=str(result))
                processed_results.append({
                    "url": url,
                    "status": "error",
                    "error": str(result),
                    "text": "",
                    "title": None,
                    "word_count": 0
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _crawl_single_url(
        self, 
        url: str, 
        render_js: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Crawl a single URL"""
        
        try:
            # Check cache first
            cache_key = f"crawl:{url}:{render_js}"
            if self.cache:
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    logger.info("Returning cached crawl result", url=url)
                    return cached_result
            
            # Check robots.txt
            crawler = self.js_crawler if render_js and self.js_crawler else self.http_crawler
            
            if not await crawler.can_crawl(url):
                logger.warning("URL blocked by robots.txt", url=url)
                return {
                    "url": url,
                    "status": "blocked",
                    "error": "Blocked by robots.txt",
                    "text": "",
                    "title": None,
                    "word_count": 0
                }
            
            # Fetch page
            page = await crawler.fetch(url, **kwargs)
            
            if page.status != 200:
                logger.warning("Non-200 status code", url=url, status=page.status)
                return {
                    "url": url,
                    "status": f"http_{page.status}",
                    "error": f"HTTP {page.status}",
                    "text": "",
                    "title": None,
                    "word_count": 0
                }
            
            # Extract content
            content = await crawler.extract(page)
            
            result = {
                "url": str(content.url),
                "status": "success",
                "text": content.text,
                "title": content.title,
                "word_count": content.word_count,
                "language": content.lang,
                "author": content.author,
                "publish_date": content.publish_date.isoformat() if content.publish_date else None,
                "metadata": content.metadata
            }
            
            # Cache successful results
            if self.cache:
                await self.cache.set(cache_key, result, ttl=3600)  # 1 hour
            
            logger.info("Crawl successful", url=url, word_count=content.word_count)
            return result
            
        except Exception as e:
            logger.error("Crawl error", url=url, error=str(e))
            raise CrawlerError(f"Failed to crawl {url}: {str(e)}")
    
    async def extract_content(self, url: str, render_js: bool = False) -> ExtractedContent:
        """Extract content from a single URL"""
        
        crawler = self.js_crawler if render_js and self.js_crawler else self.http_crawler
        
        # Check robots.txt
        if not await crawler.can_crawl(url):
            raise CrawlerError(f"URL blocked by robots.txt: {url}")
        
        # Fetch and extract
        page = await crawler.fetch(url)
        
        if page.status != 200:
            raise CrawlerError(f"HTTP {page.status} for URL: {url}")
        
        return await crawler.extract(page)
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""