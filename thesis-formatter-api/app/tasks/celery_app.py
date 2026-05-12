"""
Celery configuration and task definitions.
"""

from celery import Celery

from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "thesis_formatter",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.format_tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=settings.task_timeout,
    task_soft_time_limit=settings.task_timeout - 30,

    # Result settings
    result_expires=3600,  # 1 hour

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=settings.task_max_retries,
)
