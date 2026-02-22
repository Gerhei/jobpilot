from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.database import SyncSessionLocal
from app.models.vacancy import Vacancy
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.cleanup.cleanup_old_vacancies")
def cleanup_old_vacancies() -> dict:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)
    with SyncSessionLocal() as session:
        result = session.execute(delete(Vacancy).where(Vacancy.published_at < cutoff))
        session.commit()
    return {"deleted": result.rowcount}
