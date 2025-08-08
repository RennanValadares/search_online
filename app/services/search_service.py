import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from app.domain.contracts import SearchProvider, CacheProvider
from app.domain.models import SearchResult
from app.core.errors import SearchProviderError
from app.core.logger import get_logger

logger = get_logger(__name__)


class SearchService:
    """Service for orchestrating search across multiple providers"""
    
    def __init__(
        self, 
        providers: Dict[str, SearchProvider],
        cache: Optional[CacheProvider] = None
    ):
        self.providers = providers
        self.cache = cache
    
    async def search(
        self, 
        query: str, 
        providers: List[str], 
        num: int = 10,
        **kwargs
    ) -> List[SearchResult]:
        """Search across multiple providers and aggregate results"""
        
        if not providers:
            providers = list(self.providers.keys())
        
        # Filter to available providers
        available_providers = []
        for provider_name in providers:
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                if await provider.is_available():
                    available_providers.append(provider_name)
                else:
                    logger.warning("Provider not available", provider=provider_name)
        
        if not available_providers:
            raise SearchProviderError("No search providers available")
        
        # Check cache first
        cache_key = self._get_cache_key(query, available_providers, num, **kwargs)
        if self.cache:
            cached_results = await self.cache.get(cache_key)
            if cached_results:
                logger.info("Returning cached search results", query=query)
                return [SearchResult(**result) for result in cached_results]
        
        # Distribute search load across providers
        results_per_provider = max(1, num // len(available_providers))
        
        # Execute searches in parallel
        tasks = []
        for provider_name in available_providers:
            provider = self.providers[provider_name]
            task = self._search_with_provider(
                provider, query, results_per_provider, **kwargs
            )
            tasks.append(task)
        
        # Gather results
        provider_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine and process results
        all_results = []
        for i, result in enumerate(provider_results):
            provider_name = available_providers[i]
            
            if isinstance(result, Exception):
                logger.error("Provider search failed", 
                           provider=provider_name, 
                           error=str(result))
                continue
            
            all_results.extend(result)
        
        # Deduplicate and limit results
        deduplicated = self._deduplicate_results(all_results)
        final_results = deduplicated[:num]
        
        # Cache results
        if self.cache and final_results:
            cache_data = [result.dict() for result in final_results]
            await self.cache.set(cache_key, cache_data, ttl=1800)  # 30 minutes
        
        logger.info("Search completed", 
                   query=query, 
                   providers=available_providers,
                   total_results=len(final_results))
        
        return final_results
    
    async def _search_with_provider(
        self, 
        provider: SearchProvider, 
        query: str, 
        num: int,
        **kwargs
    ) -> List[SearchResult]:
        """Search with a single provider"""
        try:
            return await provider.search(query, num, **kwargs)
        except Exception as e:
            logger.error("Provider search error", 
                        provider=provider.__class__.__name__, 
                        error=str(e))
            return []
    
    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results based on normalized URLs"""
        seen_urls = set()
        deduplicated = []
        
        for result in results:
            normalized_url = self._normalize_url(str(result.url))
            
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                deduplicated.append(result)
        
        return deduplicated
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication"""
        try:
            parsed = urlparse(url)
            
            # Remove common tracking parameters
            query_params = parse_qs(parsed.query)
            tracking_params = {
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'msclkid', 'ref', 'source'
            }
            
            filtered_params = {
                k: v for k, v in query_params.items() 
                if k not in tracking_params
            }
            
            # Rebuild URL
            new_query = urlencode(filtered_params, doseq=True)
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path.rstrip('/'),
                parsed.params,
                new_query,
                ''  # Remove fragment
            ))
            
            return normalized
            
        except Exception:
            # If normalization fails, return original URL
            return url
    
    def _get_cache_key(
        self, 
        query: str, 
        providers: List[str], 
        num: int,
        **kwargs
    ) -> str:
        """Generate cache key for search results"""
        key_parts = [
            "search",
            query.lower().strip(),
            ",".join(sorted(providers)),
            str(num)
        ]
        
        # Add relevant kwargs to cache key
        for key in sorted(kwargs.keys()):
            if key in ['lang', 'country', 'market']:
                key_parts.append(f"{key}:{kwargs[key]}")
        
        return ":".join(key_parts)