"""
Redis configuration module.

This module defines the Redis connection settings and provides
function to create a Redis connection pool for the application.
"""

import os
import redis
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def get_redis_config():
    """
    Get Redis configuration from environment variables.

    Returns:
        dict: Redis configuration parameters
    """
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "db": int(os.getenv("REDIS_DB", 0)),
        "password": os.getenv("REDIS_PASSWORD", None),
        "ssl": os.getenv("REDIS_SSL", "false").lower() == "true",
        "key_prefix": os.getenv("REDIS_KEY_PREFIX", "a2a:"),
        "default_ttl": int(os.getenv("REDIS_TTL", 3600)),
    }


def get_a2a_config():
    """
    Get A2A-specific cache TTL values from environment variables.

    Returns:
        dict: A2A TTL configuration parameters
    """
    return {
        "task_ttl": int(os.getenv("A2A_TASK_TTL", 3600)),
        "history_ttl": int(os.getenv("A2A_HISTORY_TTL", 86400)),
        "push_notification_ttl": int(os.getenv("A2A_PUSH_NOTIFICATION_TTL", 3600)),
        "sse_client_ttl": int(os.getenv("A2A_SSE_CLIENT_TTL", 300)),
    }


def create_redis_pool(config=None):
    """
    Create and return a Redis connection pool.

    Args:
        config (dict, optional): Redis configuration. If None,
                                 configuration is loaded from environment

    Returns:
        redis.ConnectionPool: Redis connection pool
    """
    if config is None:
        config = get_redis_config()

    try:
        connection_pool = redis.ConnectionPool(
            host=config["host"],
            port=config["port"],
            db=config["db"],
            password=config["password"] if config["password"] else None,
            ssl=config["ssl"],
            decode_responses=True,
        )
        # Test the connection
        redis_client = redis.Redis(connection_pool=connection_pool)
        redis_client.ping()
        logger.info(
            f"Redis connection successful: {config['host']}:{config['port']}, "
            f"db={config['db']}, ssl={config['ssl']}"
        )
        return connection_pool
    except redis.RedisError as e:
        logger.error(f"Redis connection error: {e}")
        raise
