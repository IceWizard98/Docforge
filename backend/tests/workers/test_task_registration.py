"""Guard: every Celery task module must be registered with the worker app.

The worker boots as `celery -A workers.celery_app worker`, which imports ONLY
`workers/celery_app.py`. A `@celery_app.task` registers only when its module is
imported, so without an explicit `include=` the worker has no handler for the
dispatched tasks and silently discards them (e.g. an uploaded document stays
`uploaded` forever -> UI "In coda"). These tests fail if that wiring regresses.
"""

from workers.celery_app import celery_app

EXPECTED_TASKS = [
    "workers.classification.classify_document_task",
    "workers.drafting.generate_draft_task",
    "workers.drafting.generate_section_task",
    "workers.export.export_document_task",
]


def _worker_registry() -> set[str]:
    # Reproduce what `celery -A workers.celery_app worker` does on boot: import the
    # `include` modules. This is independent of whether the API process happened to
    # import a task module as a side effect, so it reflects the WORKER's real view.
    celery_app.loader.import_default_modules()
    return set(celery_app.tasks.keys())


def test_all_task_modules_registered_on_app():
    registered = _worker_registry()
    missing = [name for name in EXPECTED_TASKS if name not in registered]
    assert not missing, f"Celery tasks not registered with the worker app: {missing}"


def test_classify_document_task_is_registered():
    # The exact task the upload endpoint dispatches; its absence is the root
    # cause of documents stuck on "in coda".
    assert "workers.classification.classify_document_task" in _worker_registry()
