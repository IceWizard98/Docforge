import logging
import time

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from config.settings import get_settings

logger = logging.getLogger("docforge")

# Seconds to wait before retrying Redis after a connection failure. Avoids
# permanently disabling security-critical checks (token blacklist, rate
# limiting) when Redis suffers a transient outage and later recovers.
_RETRY_COOLDOWN_SECONDS = 30.0


class RedisClient:
    _instance: Redis | None = None
    _available: bool | None = None
    _last_failure: float = 0.0

    @classmethod
    async def get_client(cls) -> Redis | None:
        if cls._available is False:
            if (time.monotonic() - cls._last_failure) < _RETRY_COOLDOWN_SECONDS:
                return None
            # Cooldown elapsed: allow a fresh connection attempt below.
            cls._available = None
        if cls._instance is None:
            settings = get_settings()
            try:
                cls._instance = Redis.from_url(
                    settings.redis_url, decode_responses=True,
                    socket_connect_timeout=3, socket_timeout=3,
                )
                await cls._instance.ping()
                cls._available = True
                logger.info("Redis connection established")
            except (RedisConnectionError, RedisTimeoutError, OSError) as e:
                logger.warning(
                    "Redis unavailable (auth will skip token blacklist checks, "
                    "rate limiting disabled); retrying in %ss: %s",
                    _RETRY_COOLDOWN_SECONDS, e,
                )
                cls._available = False
                cls._last_failure = time.monotonic()
                cls._instance = None
                return None
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        if cls._instance:
            try:
                await cls._instance.close()
            except Exception:
                pass
            cls._instance = None
            cls._available = None
            cls._last_failure = 0.0
