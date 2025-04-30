"""
Cache Redis service for the A2A protocol.

This service provides an interface for storing and retrieving data related to tasks,
push notification configurations, and other A2A-related data.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
import asyncio
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from src.config.redis import get_redis_config, get_a2a_config
import threading
import time

logger = logging.getLogger(__name__)


class _InMemoryCacheFallback:
    """
    Fallback in-memory cache implementation for when Redis is not available.

    This should only be used for development or testing environments.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize cache storage."""
        if not getattr(self, "_initialized", False):
            with self._lock:
                if not getattr(self, "_initialized", False):
                    self._data = {}
                    self._ttls = {}
                    self._hash_data = {}
                    self._list_data = {}
                    self._data_lock = threading.Lock()
                    self._initialized = True
                    logger.warning(
                        "Initializing in-memory cache fallback (not for production)"
                    )

    async def set(self, key, value, ex=None):
        """Set a key with optional expiration."""
        with self._data_lock:
            self._data[key] = value
            if ex is not None:
                self._ttls[key] = time.time() + ex
            elif key in self._ttls:
                del self._ttls[key]
        return True

    async def setex(self, key, ex, value):
        """Set a key with expiration."""
        return await self.set(key, value, ex)

    async def get(self, key):
        """Get a key value."""
        with self._data_lock:
            # Check if expired
            if key in self._ttls and time.time() > self._ttls[key]:
                del self._data[key]
                del self._ttls[key]
                return None
            return self._data.get(key)

    async def delete(self, key):
        """Delete a key."""
        with self._data_lock:
            if key in self._data:
                del self._data[key]
                if key in self._ttls:
                    del self._ttls[key]
                return 1
            return 0

    async def exists(self, key):
        """Check if key exists."""
        with self._data_lock:
            if key in self._ttls and time.time() > self._ttls[key]:
                del self._data[key]
                del self._ttls[key]
                return 0
            return 1 if key in self._data else 0

    async def hset(self, key, field, value):
        """Set a hash field."""
        with self._data_lock:
            if key not in self._hash_data:
                self._hash_data[key] = {}
            self._hash_data[key][field] = value
        return 1

    async def hget(self, key, field):
        """Get a hash field."""
        with self._data_lock:
            if key not in self._hash_data:
                return None
            return self._hash_data[key].get(field)

    async def hdel(self, key, field):
        """Delete a hash field."""
        with self._data_lock:
            if key in self._hash_data and field in self._hash_data[key]:
                del self._hash_data[key][field]
                return 1
            return 0

    async def hgetall(self, key):
        """Get all hash fields."""
        with self._data_lock:
            if key not in self._hash_data:
                return {}
            return dict(self._hash_data[key])

    async def rpush(self, key, value):
        """Add to a list."""
        with self._data_lock:
            if key not in self._list_data:
                self._list_data[key] = []
            self._list_data[key].append(value)
            return len(self._list_data[key])

    async def lrange(self, key, start, end):
        """Get range from list."""
        with self._data_lock:
            if key not in self._list_data:
                return []

            # Handle negative indices
            if end < 0:
                end = len(self._list_data[key]) + end + 1

            return self._list_data[key][start:end]

    async def expire(self, key, seconds):
        """Set expiration on key."""
        with self._data_lock:
            if key in self._data:
                self._ttls[key] = time.time() + seconds
                return 1
            return 0

    async def flushdb(self):
        """Clear all data."""
        with self._data_lock:
            self._data.clear()
            self._ttls.clear()
            self._hash_data.clear()
            self._list_data.clear()
        return True

    async def keys(self, pattern="*"):
        """Get keys matching pattern."""
        with self._data_lock:
            # Clean expired keys
            now = time.time()
            expired_keys = [k for k, exp in self._ttls.items() if now > exp]
            for k in expired_keys:
                if k in self._data:
                    del self._data[k]
                del self._ttls[k]

            # Simple pattern matching
            result = []
            if pattern == "*":
                result = list(self._data.keys())
            elif pattern.endswith("*"):
                prefix = pattern[:-1]
                result = [k for k in self._data.keys() if k.startswith(prefix)]
            elif pattern.startswith("*"):
                suffix = pattern[1:]
                result = [k for k in self._data.keys() if k.endswith(suffix)]
            else:
                if pattern in self._data:
                    result = [pattern]

            return result

    async def ping(self):
        """Test connection."""
        return True


class RedisCacheService:
    """
    Cache service using Redis for storing A2A-related data.

    This implementation uses a real Redis connection for distributed caching
    and data persistence across multiple instances.

    If Redis is not available, falls back to an in-memory implementation.
    """

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize the Redis cache service.

        Args:
            redis_url: Redis server URL (optional, defaults to config value)
        """
        if redis_url:
            self._redis_url = redis_url
        else:
            # Construir URL a partir dos componentes de configuração
            config = get_redis_config()
            protocol = "rediss" if config.get("ssl", False) else "redis"
            auth = f":{config['password']}@" if config.get("password") else ""
            self._redis_url = (
                f"{protocol}://{auth}{config['host']}:{config['port']}/{config['db']}"
            )

        self._redis = None
        self._in_memory_mode = False
        self._connecting = False
        self._connection_lock = asyncio.Lock()
        logger.info(f"Initializing RedisCacheService with URL: {self._redis_url}")

    async def _get_redis(self):
        """
        Get a Redis connection, creating it if necessary.
        Falls back to in-memory implementation if Redis is not available.

        Returns:
            Redis connection or in-memory fallback
        """
        if self._redis is not None:
            return self._redis

        async with self._connection_lock:
            if self._redis is None and not self._connecting:
                try:
                    self._connecting = True
                    logger.info(f"Connecting to Redis at {self._redis_url}")
                    self._redis = aioredis.from_url(
                        self._redis_url, encoding="utf-8", decode_responses=True
                    )
                    # Teste de conexão
                    await self._redis.ping()
                    logger.info("Redis connection successful")
                except Exception as e:
                    logger.error(f"Error connecting to Redis: {str(e)}")
                    logger.warning(
                        "Falling back to in-memory cache (not suitable for production)"
                    )
                    self._redis = _InMemoryCacheFallback()
                    self._in_memory_mode = True
                finally:
                    self._connecting = False

        return self._redis

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store a value in the cache.

        Args:
            key: Key for the value
            value: Value to store
            ttl: Time to live in seconds (optional)
        """
        try:
            redis = await self._get_redis()

            # Convert dict/list to JSON string
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            if ttl:
                await redis.setex(key, ttl, value)
            else:
                await redis.set(key, value)

            logger.debug(f"Set cache key: {key}")
        except Exception as e:
            logger.error(f"Error setting Redis key {key}: {str(e)}")

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the cache.

        Args:
            key: Key for the value to retrieve

        Returns:
            The stored value or None if not found
        """
        try:
            redis = await self._get_redis()
            value = await redis.get(key)

            if value is None:
                return None

            try:
                # Try to parse as JSON
                return json.loads(value)
            except json.JSONDecodeError:
                # Return as-is if not JSON
                return value

        except Exception as e:
            logger.error(f"Error getting Redis key {key}: {str(e)}")
            return None

    async def delete(self, key: str) -> bool:
        """
        Remove a value from the cache.

        Args:
            key: Key for the value to remove

        Returns:
            True if the value was removed, False if it didn't exist
        """
        try:
            redis = await self._get_redis()
            result = await redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting Redis key {key}: {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key: Key to check

        Returns:
            True if the key exists, False otherwise
        """
        try:
            redis = await self._get_redis()
            return await redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking Redis key {key}: {str(e)}")
            return False

    async def set_hash(self, key: str, field: str, value: Any) -> None:
        """
        Store a value in a hash.

        Args:
            key: Hash key
            field: Hash field
            value: Value to store
        """
        try:
            redis = await self._get_redis()

            # Convert dict/list to JSON string
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            await redis.hset(key, field, value)
            logger.debug(f"Set hash field: {key}:{field}")
        except Exception as e:
            logger.error(f"Error setting Redis hash {key}:{field}: {str(e)}")

    async def get_hash(self, key: str, field: str) -> Optional[Any]:
        """
        Retrieve a value from a hash.

        Args:
            key: Hash key
            field: Hash field

        Returns:
            The stored value or None if not found
        """
        try:
            redis = await self._get_redis()
            value = await redis.hget(key, field)

            if value is None:
                return None

            try:
                # Try to parse as JSON
                return json.loads(value)
            except json.JSONDecodeError:
                # Return as-is if not JSON
                return value

        except Exception as e:
            logger.error(f"Error getting Redis hash {key}:{field}: {str(e)}")
            return None

    async def delete_hash(self, key: str, field: str) -> bool:
        """
        Remove a value from a hash.

        Args:
            key: Hash key
            field: Hash field

        Returns:
            True if the value was removed, False if it didn't exist
        """
        try:
            redis = await self._get_redis()
            result = await redis.hdel(key, field)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting Redis hash {key}:{field}: {str(e)}")
            return False

    async def get_all_hash(self, key: str) -> Dict[str, Any]:
        """
        Retrieve all values from a hash.

        Args:
            key: Hash key

        Returns:
            Dictionary with all hash values
        """
        try:
            redis = await self._get_redis()
            result_dict = await redis.hgetall(key)

            if not result_dict:
                return {}

            # Try to parse each value as JSON
            parsed_dict = {}
            for field, value in result_dict.items():
                try:
                    parsed_dict[field] = json.loads(value)
                except json.JSONDecodeError:
                    parsed_dict[field] = value

            return parsed_dict

        except Exception as e:
            logger.error(f"Error getting all Redis hash fields for {key}: {str(e)}")
            return {}

    async def push_list(self, key: str, value: Any) -> int:
        """
        Add a value to the end of a list.

        Args:
            key: List key
            value: Value to add

        Returns:
            Size of the list after the addition
        """
        try:
            redis = await self._get_redis()

            # Convert dict/list to JSON string
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            return await redis.rpush(key, value)
        except Exception as e:
            logger.error(f"Error pushing to Redis list {key}: {str(e)}")
            return 0

    async def get_list(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """
        Retrieve values from a list.

        Args:
            key: List key
            start: Initial index (inclusive)
            end: Final index (inclusive), -1 for all

        Returns:
            List with the retrieved values
        """
        try:
            redis = await self._get_redis()
            values = await redis.lrange(key, start, end)

            if not values:
                return []

            # Try to parse each value as JSON
            result = []
            for value in values:
                try:
                    result.append(json.loads(value))
                except json.JSONDecodeError:
                    result.append(value)

            return result

        except Exception as e:
            logger.error(f"Error getting Redis list {key}: {str(e)}")
            return []

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set a time-to-live for a key.

        Args:
            key: Key
            ttl: Time-to-live in seconds

        Returns:
            True if the key exists and the TTL was set, False otherwise
        """
        try:
            redis = await self._get_redis()
            return await redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"Error setting expire for Redis key {key}: {str(e)}")
            return False

    async def clear(self) -> None:
        """
        Clear the entire cache.

        Warning: This is a destructive operation and will remove all data.
        Only use in development/test environments.
        """
        try:
            redis = await self._get_redis()
            await redis.flushdb()
            logger.warning("Redis database flushed - all data cleared")
        except Exception as e:
            logger.error(f"Error clearing Redis database: {str(e)}")

    async def keys(self, pattern: str = "*") -> List[str]:
        """
        Retrieve keys that match a pattern.

        Args:
            pattern: Glob pattern to filter keys

        Returns:
            List of keys that match the pattern
        """
        try:
            redis = await self._get_redis()
            return await redis.keys(pattern)
        except Exception as e:
            logger.error(f"Error getting Redis keys with pattern {pattern}: {str(e)}")
            return []
