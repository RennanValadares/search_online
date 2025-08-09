import json
import redis.asyncio as redis
from typing import Any, Optional, Dict

from app.domain.contracts import CacheProvider
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class RedisCache(CacheProvider):
    """Redis-based cache implementation"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("Connected to Redis", url=self.redis_url)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            self.redis_client = None
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value is None:
                return None
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
                
        except Exception as e:
            logger.error("Cache get error", key=key, error=str(e))
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        if not self.redis_client:
            return
        
        try:
            # Serialize to JSON if not string
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
            
            if ttl:
                await self.redis_client.setex(key, ttl, serialized_value)
            else:
                await self.redis_client.set(key, serialized_value)
                
        except Exception as e:
            logger.error("Cache set error", key=key, error=str(e))
    
    async def delete(self, key: str) -> None:
        """Delete value from cache"""
        if not self.redis_client:
            return
        
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error("Cache delete error", key=key, error=str(e))
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.redis_client:
            return False
        
        try:
            return bool(await self.redis_client.exists(key))
        except Exception as e:
            logger.error("Cache exists error", key=key, error=str(e))
            return False


class MemoryCache(CacheProvider):
    """Simple in-memory cache for development/testing"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        return self._cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache (TTL ignored in memory cache)"""
        self._cache[key] = value
    
    async def delete(self, key: str) -> None:
        """Delete value from cache"""
        self._cache.pop(key, None)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return key in self._cache
    
    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()
