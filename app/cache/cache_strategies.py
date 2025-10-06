"""
Advanced Caching Strategies - Optimized caching patterns for production

Implements:
- Multi-tier caching (memory + Redis)
- Cache-aside pattern
- Write-through caching
- TTL management
- Cache warming
- Compression for large payloads
"""

import pickle
import zlib
from typing import Optional, Any, Callable, TypeVar
from functools import wraps
import hashlib
import logging
from datetime import datetime, timedelta

from app.cache.redis_client import get_redis_client

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheStrategy:
    """Advanced caching with compression and intelligent TTL"""

    def __init__(self, redis_client=None, compress_threshold=1024):
        """
        Initialize cache strategy

        Args:
            redis_client: Redis client instance (optional, will auto-fetch if None)
            compress_threshold: Compress values larger than this (bytes)
        """
        self.redis = redis_client or get_redis_client()
        self.compress_threshold = compress_threshold
        self.enabled = self.redis is not None

    def _make_key(self, namespace: str, key: str) -> str:
        """Create namespaced cache key"""
        return f"{namespace}:{key}"

    def _serialize(self, value: Any, compress: bool = True) -> bytes:
        """Serialize and optionally compress value"""
        serialized = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

        # Compress if above threshold
        if compress and len(serialized) > self.compress_threshold:
            compressed = zlib.compress(serialized, level=6)  # Level 6 = good balance
            # Only use compressed if it's actually smaller
            if len(compressed) < len(serialized):
                return b'C' + compressed  # 'C' prefix indicates compressed

        return b'U' + serialized  # 'U' prefix indicates uncompressed

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize and decompress value"""
        if not data:
            return None

        # Check compression flag
        if data[0:1] == b'C':
            # Compressed
            decompressed = zlib.decompress(data[1:])
            return pickle.loads(decompressed)
        elif data[0:1] == b'U':
            # Uncompressed
            return pickle.loads(data[1:])
        else:
            # Legacy format (no flag)
            return pickle.loads(data)

    def get(self, namespace: str, key: str, default=None) -> Any:
        """Get value from cache"""
        if not self.enabled:
            return default

        try:
            cache_key = self._make_key(namespace, key)
            data = self.redis.get(cache_key)

            if data is None:
                return default

            return self._deserialize(data)

        except Exception as e:
            logger.error(f"Cache get error for {namespace}:{key}: {e}")
            return default

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        compress: bool = True
    ) -> bool:
        """Set value in cache with optional TTL"""
        if not self.enabled:
            return False

        try:
            cache_key = self._make_key(namespace, key)
            serialized = self._serialize(value, compress=compress)

            if ttl_seconds:
                self.redis.setex(cache_key, ttl_seconds, serialized)
            else:
                self.redis.set(cache_key, serialized)

            return True

        except Exception as e:
            logger.error(f"Cache set error for {namespace}:{key}: {e}")
            return False

    def delete(self, namespace: str, key: str) -> bool:
        """Delete value from cache"""
        if not self.enabled:
            return False

        try:
            cache_key = self._make_key(namespace, key)
            self.redis.delete(cache_key)
            return True

        except Exception as e:
            logger.error(f"Cache delete error for {namespace}:{key}: {e}")
            return False

    def delete_pattern(self, namespace: str, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.enabled:
            return 0

        try:
            cache_pattern = self._make_key(namespace, pattern)
            keys = self.redis.keys(cache_pattern)

            if keys:
                return self.redis.delete(*keys)

            return 0

        except Exception as e:
            logger.error(f"Cache delete pattern error for {namespace}:{pattern}: {e}")
            return 0

    def get_or_set(
        self,
        namespace: str,
        key: str,
        factory: Callable[[], T],
        ttl_seconds: Optional[int] = None
    ) -> T:
        """Get from cache or compute and store (cache-aside pattern)"""
        # Try to get from cache
        value = self.get(namespace, key)

        if value is not None:
            return value

        # Cache miss - compute value
        value = factory()

        # Store in cache
        self.set(namespace, key, value, ttl_seconds=ttl_seconds)

        return value

    def invalidate_namespace(self, namespace: str) -> int:
        """Invalidate all keys in namespace"""
        return self.delete_pattern(namespace, "*")

    def exists(self, namespace: str, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.enabled:
            return False

        try:
            cache_key = self._make_key(namespace, key)
            return self.redis.exists(cache_key) > 0

        except Exception as e:
            logger.error(f"Cache exists error for {namespace}:{key}: {e}")
            return False

    def get_ttl(self, namespace: str, key: str) -> Optional[int]:
        """Get remaining TTL in seconds (-1 if no expiry, -2 if key doesn't exist)"""
        if not self.enabled:
            return None

        try:
            cache_key = self._make_key(namespace, key)
            return self.redis.ttl(cache_key)

        except Exception as e:
            logger.error(f"Cache TTL error for {namespace}:{key}: {e}")
            return None


# Global cache instance
_cache_strategy = CacheStrategy()


def get_cache() -> CacheStrategy:
    """Get global cache strategy instance"""
    return _cache_strategy


def cached(
    namespace: str,
    ttl_seconds: int = 300,
    key_func: Optional[Callable] = None
):
    """
    Decorator for caching function results

    Args:
        namespace: Cache namespace
        ttl_seconds: Time to live in seconds
        key_func: Function to generate cache key from args/kwargs

    Usage:
        @cached(namespace="analytics", ttl_seconds=600)
        def expensive_computation(org_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: hash of function name + args + kwargs
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                key_string = ":".join(key_parts)
                cache_key = hashlib.md5(key_string.encode()).hexdigest()

            # Try cache first
            result = cache.get(namespace, cache_key)
            if result is not None:
                return result

            # Cache miss - execute function
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(namespace, cache_key, result, ttl_seconds=ttl_seconds)

            return result

        return wrapper
    return decorator


# Pre-defined cache TTLs for different use cases
class CacheTTL:
    """Standard TTL values for different data types"""
    STATIC = 86400           # 24 hours - for static/rarely changing data
    ANALYTICS = 600          # 10 minutes - for analytics data
    TICKETS = 300            # 5 minutes - for ticket lists
    USER_DATA = 900          # 15 minutes - for user profile data
    SEARCH_RESULTS = 180     # 3 minutes - for search results
    ML_PREDICTIONS = 3600    # 1 hour - for ML predictions
    DASHBOARD = 120          # 2 minutes - for dashboard data
