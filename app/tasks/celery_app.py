from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "jobpilot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    imports=["app.tasks.fetch", "app.tasks.enrich", "app.tasks.cleanup"],
    beat_schedule={
        "fetch-vacancies-hourly": {
            "task": "app.tasks.fetch.fetch_vacancies",
            "schedule": crontab(minute=0),  # каждый час
        },
        "cleanup-old-vacancies-daily": {
            "task": "app.tasks.cleanup.cleanup_old_vacancies",
            "schedule": crontab(hour=2, minute=0),  # ежедневно в 2:00 UTC
        },
    },
)
