import httpx
import trafilatura
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
from typing import Optional
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.contracts import Crawler
from app.domain.models import Page, ExtractedContent
from app.core.errors import CrawlerError
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class HttpCrawler(Crawler):
    """HTTP-based crawler using trafilatura for content extraction"""
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.robots_cache = {}  # Simple in-memory cache for robots.txt
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8)
    )
    async def fetch(self, url: str, **kwargs) -> Page:
        """Fetch a page via HTTP"""
        
        headers = {
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Override headers if provided
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
        
        try:
            logger.info("Fetching URL", url=url)
            
            response = await self.client.get(
                url,
                headers=headers,
                timeout=settings.http_timeout,
                follow_redirects=True
            )
            
            page = Page(
                url=url,
                status=response.status_code,
                html=response.text if response.status_code == 200 else None,
                final_url=str(response.url),
                headers=dict(response.headers),
                fetch_time=datetime.utcnow()
            )
            
            logger.info("Page fetched", url=url, status=response.status_code, 
                       final_url=str(response.url))
            
            return page
            
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error fetching page", url=url, status=e.response.status_code)
            return Page(
                url=url,
                status=e.response.status_code,
                final_url=str(e.response.url) if e.response else url,
                fetch_time=datetime.utcnow()
            )
        except httpx.RequestError as e:
            logger.error("Request error fetching page", url=url, error=str(e))
            raise CrawlerError(f"Failed to fetch {url}: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error fetching page", url=url, error=str(e))
            raise CrawlerError(f"Unexpected error fetching {url}: {str(e)}")
    
    async def extract(self, page: Page) -> ExtractedContent:
        """Extract content from page using trafilatura"""
        
        if not page.html:
            logger.warning("No HTML content to extract", url=page.url)
            return ExtractedContent(
                url=page.final_url or page.url,
                text="",
                word_count=0
            )
        
        try:
            logger.info("Extracting content", url=page.url)
            
            # Extract main text content
            text = trafilatura.extract(
                page.html,
                include_comments=False,
                include_tables=True,
                include_formatting=False
            ) or ""
            
            # Extract metadata
            metadata = trafilatura.extract_metadata(page.html)
            
            content = ExtractedContent(
                url=page.final_url or page.url,
                text=text,
                title=metadata.title if metadata else None,
                lang=metadata.language if metadata else None,
                author=metadata.author if metadata else None,
                publish_date=metadata.date if metadata else None,
                word_count=len(text.split()) if text else 0,
                metadata={
                    "description": metadata.description if metadata else None,
                    "sitename": metadata.sitename if metadata else None,
                    "categories": metadata.categories if metadata else None,
                    "tags": metadata.tags if metadata else None,
                }
            )
            
            logger.info("Content extracted", url=page.url, word_count=content.word_count)
            return content
            
        except Exception as e:
            logger.error("Error extracting content", url=page.url, error=str(e))
            raise CrawlerError(f"Failed to extract content from {page.url}: {str(e)}")
    
    async def can_crawl(self, url: str) -> bool:
        """Check if URL can be crawled according to robots.txt"""
        
        try:
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            robots_url = urljoin(base_url, "/robots.txt")
            
            # Check cache first
            if robots_url in self.robots_cache:
                rp = self.robots_cache[robots_url]
            else:
                # Fetch and parse robots.txt
                try:
                    response = await self.client.get(robots_url, timeout=5.0)
                    if response.status_code == 200:
                        rp = RobotFileParser()
                        rp.set_url(robots_url)
                        rp.read()  # This doesn't work with async, need to use feed
                        # Workaround: manually parse
                        lines = response.text.split('\n')
                        rp.feed(lines)
                        self.robots_cache[robots_url] = rp
                    else:
                        # No robots.txt or error - assume allowed
                        return True
                except Exception:
                    # Error fetching robots.txt - assume allowed
                    return True
            
            # Check if our user agent can fetch this URL
            return rp.can_fetch(settings.user_agent, url)
            
        except Exception as e:
            logger.warning("Error checking robots.txt", url=url, error=str(e))
            # On error, assume allowed
            return True