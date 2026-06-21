from celery import Celery

from config.settings import get_settings

settings = get_settings()
celery_app = Celery("docforge", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Tasks are fire-and-forget (dispatched via .delay/.apply_async, never .get()).
    # They return DomainEvent dataclasses which the JSON result serializer cannot
    # encode; ignoring results avoids EncodeError marking succeeded tasks FAILURE.
    task_ignore_result=True,
    timezone="Europe/Rome",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=300,
    task_max_retries=3,
    worker_prefetch_multiplier=1,
)



