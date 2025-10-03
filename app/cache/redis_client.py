import os
from typing import Optional

try:
    from redis import Redis, ConnectionPool
    from redis.exceptions import RedisError
except ImportError:
    Redis = None
    ConnectionPool = None
    RedisError = Exception


_redis_client: Optional[Redis] = None
_connection_pool: Optional[ConnectionPool] = None


def get_redis_client() -> Optional[Redis]:
    """
    Get Redis client instance (singleton pattern)
    Returns None if Redis is not configured or connection fails
    """
    global _redis_client, _connection_pool

    if _redis_client is not None:
        return _redis_client

    if Redis is None:
        print("Redis module not installed. Install with: pip install redis")
        return None

    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

        if not redis_url:
            print("Redis URL not configured")
            return None

        # Create connection pool
        _connection_pool = ConnectionPool.from_url(
            redis_url,
            max_connections=10,
            decode_responses=False  # We'll handle encoding/decoding manually
        )

        # Create Redis client
        _redis_client = Redis(connection_pool=_connection_pool)

        # Test connection
        _redis_client.ping()
        print(f"Redis connected successfully: {redis_url}")

        return _redis_client

    except RedisError as e:
        print(f"Redis connection error: {e}")
        _redis_client = None
        return None
    except Exception as e:
        print(f"Unexpected error connecting to Redis: {e}")
        _redis_client = None
        return None


def close_redis_connection():
    """Close Redis connection"""
    global _redis_client, _connection_pool

    if _redis_client:
        _redis_client.close()
        _redis_client = None

    if _connection_pool:
        _connection_pool.disconnect()
        _connection_pool = None

    print("Redis connection closed")


def reset_redis_client():
    """Reset Redis client (useful for testing)"""
    global _redis_client, _connection_pool

    close_redis_connection()
    _redis_client = None
    _connection_pool = None
