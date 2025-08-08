from typing import Any, Dict, Optional


class SearchAPIError(Exception):
    """Base exception for SearchAPI"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class SearchProviderError(SearchAPIError):
    """Error from search provider"""
    pass


class CrawlerError(SearchAPIError):
    """Error during crawling/scraping"""
    pass


class LLMError(SearchAPIError):
    """Error from LLM provider"""
    pass


class RateLimitError(SearchAPIError):
    """Rate limit exceeded"""
    pass


class ValidationError(SearchAPIError):
    """Input validation error"""
    pass


class ConfigurationError(SearchAPIError):
    """Configuration error"""
    pass