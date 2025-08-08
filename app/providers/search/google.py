import httpx
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from app.domain.contracts import SearchProvider as SearchProviderContract
from app.domain.models import SearchResult, SearchProvider
from app.core.errors import SearchProviderError
from app.core.logger import get_logger

logger = get_logger(__name__)


class GoogleSearchProvider(SearchProviderContract):
    """Google Custom Search Engine provider"""
    
    def __init__(self, api_key: str, cx: str, client: httpx.AsyncClient):
        self.api_key = api_key
        self.cx = cx
        self.client = client
        self.base_url = "https://www.googleapis.com/customsearch/v1"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def search(self, query: str, num: int = 10, **kwargs) -> List[SearchResult]:
        """Search using Google Custom Search API"""
        
        if not self.api_key or not self.cx:
            raise SearchProviderError("Google API key or CX not configured")
        
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": min(num, 10),  # Google CSE max is 10
            "safe": "active"
        }
        
        # Add optional parameters
        if "lang" in kwargs:
            params["lr"] = f"lang_{kwargs['lang']}"
        if "country" in kwargs:
            params["cr"] = f"country{kwargs['country']}"
        
        try:
            logger.info("Making Google search request", query=query, num=num)
            
            response = await self.client.get(
                self.base_url,
                params=params,
                timeout=8.0
            )
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
            
            results = []
            for i, item in enumerate(items):
                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link"),
                    snippet=item.get("snippet"),
                    provider=SearchProvider.GOOGLE,
                    rank=i + 1,
                    metadata={
                        "display_link": item.get("displayLink"),
                        "formatted_url": item.get("formattedUrl")
                    }
                )
                results.append(result)
            
            logger.info("Google search completed", results_count=len(results))
            return results
            
        except httpx.HTTPStatusError as e:
            logger.error("Google search HTTP error", status_code=e.response.status_code)
            raise SearchProviderError(f"Google search failed: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("Google search request error", error=str(e))
            raise SearchProviderError(f"Google search request failed: {str(e)}")
        except Exception as e:
            logger.error("Google search unexpected error", error=str(e))
            raise SearchProviderError(f"Google search failed: {str(e)}")
    
    async def is_available(self) -> bool:
        """Check if Google search is available"""
        return bool(self.api_key and self.cx)