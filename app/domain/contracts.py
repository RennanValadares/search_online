from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .models import SearchResult, Page, ExtractedContent, LLMMessage, LLMResponse


class SearchProvider(ABC):
    """Abstract base class for search providers"""
    
    @abstractmethod
    async def search(self, query: str, num: int = 10, **kwargs) -> List[SearchResult]:
        """Search for results"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available"""
        pass


class Crawler(ABC):
    """Abstract base class for crawlers"""
    
    @abstractmethod
    async def fetch(self, url: str, **kwargs) -> Page:
        """Fetch a page"""
        pass
    
    @abstractmethod
    async def extract(self, page: Page) -> ExtractedContent:
        """Extract content from page"""
        pass
    
    @abstractmethod
    async def can_crawl(self, url: str) -> bool:
        """Check if URL can be crawled (robots.txt)"""
        pass


class LLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    async def complete(
        self, 
        messages: List[LLMMessage], 
        model: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if client is available"""
        pass


class Reranker(ABC):
    """Abstract base class for rerankers"""
    
    @abstractmethod
    async def rerank(
        self, 
        query: str, 
        documents: List[SearchResult], 
        top_k: Optional[int] = None
    ) -> List[SearchResult]:
        """Rerank documents by relevance"""
        pass


class CacheProvider(ABC):
    """Abstract base class for cache providers"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        pass