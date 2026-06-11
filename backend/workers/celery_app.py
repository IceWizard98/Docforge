import asyncio
from functools import wraps

from celery import Celery

from config.settings import get_settings

settings = get_settings()
celery_app = Celery("docforge", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Rome",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=300,
    task_max_retries=3,
    worker_prefetch_multiplier=1,
)


def async_task(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper
