from typing import Optional, Any
import json

try:
    from redis import Redis
except ImportError:
    Redis = None


class CacheManager:
    """Manager for Redis cache operations"""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def get(self, key: str) -> Optional[str]:
        """Get value from cache"""
        try:
            if self.redis:
                value = self.redis.get(key)
                return value.decode('utf-8') if value else None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None

    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        try:
            if self.redis:
                return self.redis.setex(key, ttl, value)
        except Exception as e:
            print(f"Cache set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if self.redis:
                return self.redis.delete(key) > 0
        except Exception as e:
            print(f"Cache delete error: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            if self.redis:
                keys = self.redis.keys(pattern)
                if keys:
                    return self.redis.delete(*keys)
                return 0
        except Exception as e:
            print(f"Cache delete pattern error: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            if self.redis:
                return self.redis.exists(key) > 0
        except Exception as e:
            print(f"Cache exists error: {e}")
            return False

    def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value from cache"""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    def set_json(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set JSON value in cache"""
        try:
            json_str = json.dumps(value)
            return self.set(key, json_str, ttl)
        except Exception as e:
            print(f"Cache set JSON error: {e}")
            return False

    def clear_all(self) -> bool:
        """Clear all keys (use with caution)"""
        try:
            if self.redis:
                self.redis.flushdb()
                return True
        except Exception as e:
            print(f"Cache clear all error: {e}")
            return False

    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        try:
            if self.redis:
                return self.redis.ttl(key)
        except Exception as e:
            print(f"Cache get TTL error: {e}")
            return -1

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment value"""
        try:
            if self.redis:
                return self.redis.incrby(key, amount)
        except Exception as e:
            print(f"Cache increment error: {e}")
            return None

    def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on existing key"""
        try:
            if self.redis:
                return self.redis.expire(key, ttl)
        except Exception as e:
            print(f"Cache expire error: {e}")
            return False
