import logging

from redis.asyncio import Redis

from config.settings import get_settings

logger = logging.getLogger("docforge")


class RedisClient:
    _instance: Redis | None = None

    @classmethod
    async def get_client(cls) -> Redis:
        if cls._instance is None:
            settings = get_settings()
            cls._instance = Redis.from_url(settings.redis_url, decode_responses=True)
            await cls._instance.ping()
            logger.info("Redis connection established")
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
