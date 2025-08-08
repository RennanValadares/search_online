import httpx
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.contracts import SearchProvider as SearchProviderContract
from app.domain.models import SearchResult, SearchProvider
from app.core.errors import SearchProviderError
from app.core.logger import get_logger

logger = get_logger(__name__)


class BingSearchProvider(SearchProviderContract):
    """Bing Web Search API provider"""
    
    def __init__(self, api_key: str, client: httpx.AsyncClient):
        self.api_key = api_key
        self.client = client
        self.base_url = "https://api.bing.microsoft.com/v7.0/search"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def search(self, query: str, num: int = 10, **kwargs) -> List[SearchResult]:
        """Search using Bing Web Search API"""
        
        if not self.api_key:
            raise SearchProviderError("Bing API key not configured")
        
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key
        }
        
        params = {
            "q": query,
            "count": min(num, 50),  # Bing max is 50
            "safeSearch": "Moderate",
            "textDecorations": False,
            "textFormat": "Raw"
        }
        
        # Add optional parameters
        if "market" in kwargs:
            params["mkt"] = kwargs["market"]
        if "lang" in kwargs:
            params["setLang"] = kwargs["lang"]
        
        try:
            logger.info("Making Bing search request", query=query, num=num)
            
            response = await self.client.get(
                self.base_url,
                headers=headers,
                params=params,
                timeout=8.0
            )
            response.raise_for_status()
            
            data = response.json()
            web_pages = data.get("webPages", {}).get("value", [])
            
            results = []
            for i, item in enumerate(web_pages):
                result = SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url"),
                    snippet=item.get("snippet"),
                    provider=SearchProvider.BING,
                    rank=i + 1,
                    metadata={
                        "display_url": item.get("displayUrl"),
                        "date_last_crawled": item.get("dateLastCrawled")
                    }
                )
                results.append(result)
            
            logger.info("Bing search completed", results_count=len(results))
            return results
            
        except httpx.HTTPStatusError as e:
            logger.error("Bing search HTTP error", status_code=e.response.status_code)
            raise SearchProviderError(f"Bing search failed: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("Bing search request error", error=str(e))
            raise SearchProviderError(f"Bing search request failed: {str(e)}")
        except Exception as e:
            logger.error("Bing search unexpected error", error=str(e))
            raise SearchProviderError(f"Bing search failed: {str(e)}")
    
    async def is_available(self) -> bool:
        """Check if Bing search is available"""
        return bool(self.api_key)