from celery import Celery

from config.settings import get_settings

settings = get_settings()
# `include` makes the WORKER process import every task module on startup. Without
# it, `celery -A workers.celery_app worker` imports only this file, so the
# @celery_app.task tasks are never registered and dispatched messages are silently
# discarded (e.g. uploaded docs stuck on "in coda"). autodiscover_tasks() would not
# work here: the tasks live in workers/<name>.py, not the default workers/tasks.py.
celery_app = Celery(
    "docforge",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "workers.classification",
        "workers.drafting",
        "workers.export",
    ],
)
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
    # Reap wedged tasks so a hung LLM/embeddings/DB call can't occupy a worker slot
    # forever. Soft limit raises SoftTimeLimitExceeded (catchable); hard limit kills
    # the worker child. Generous, since local-model drafting is genuinely slow.
    task_soft_time_limit=900,   # 15 min
    task_time_limit=1020,       # 17 min hard ceiling
)



