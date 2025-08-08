from playwright.async_api import async_playwright, Browser, Page as PlaywrightPage
from typing import Optional
from datetime import datetime

from app.domain.contracts import Crawler
from app.domain.models import Page, ExtractedContent
from app.core.errors import CrawlerError
from app.core.logger import get_logger
from app.core.config import settings
from .http_crawler import HttpCrawler

logger = get_logger(__name__)


class PlaywrightCrawler(Crawler):
    """Playwright-based crawler for JavaScript-heavy sites"""
    
    def __init__(self, http_crawler: HttpCrawler):
        self.http_crawler = http_crawler
        self.browser: Optional[Browser] = None
        self._playwright = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def fetch(self, url: str, **kwargs) -> Page:
        """Fetch a page using Playwright (for JS-heavy sites)"""
        
        if not self.browser:
            raise CrawlerError("Playwright browser not initialized. Use as async context manager.")
        
        page: Optional[PlaywrightPage] = None
        
        try:
            logger.info("Fetching URL with Playwright", url=url)
            
            page = await self.browser.new_page()
            
            # Set user agent
            await page.set_user_agent(settings.user_agent)
            
            # Set viewport
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            # Navigate to page
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=settings.playwright_timeout
            )
            
            # Wait a bit for dynamic content
            await page.wait_for_timeout(2000)
            
            # Get final URL and content
            final_url = page.url
            html = await page.content()
            status = response.status if response else 0
            
            result = Page(
                url=url,
                status=status,
                html=html,
                final_url=final_url,
                fetch_time=datetime.utcnow()
            )
            
            logger.info("Page fetched with Playwright", url=url, status=status, final_url=final_url)
            return result
            
        except Exception as e:
            logger.error("Error fetching page with Playwright", url=url, error=str(e))
            raise CrawlerError(f"Playwright fetch failed for {url}: {str(e)}")
        finally:
            if page:
                await page.close()
    
    async def extract(self, page: Page) -> ExtractedContent:
        """Extract content from page (delegates to HTTP crawler)"""
        return await self.http_crawler.extract(page)
    
    async def can_crawl(self, url: str) -> bool:
        """Check if URL can be crawled (delegates to HTTP crawler)"""
        return await self.http_crawler.can_crawl(url)