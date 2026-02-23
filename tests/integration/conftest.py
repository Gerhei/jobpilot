import pytest
import redis as redis_lib
from sqlalchemy import text

from app.config import settings


@pytest.fixture(autouse=True)
def db_session():
    """Откатывает изменения после каждого теста (чистая БД)."""
    from app.database import SyncSessionLocal

    with SyncSessionLocal() as session:
        yield session
        session.execute(
            text(
                "TRUNCATE vacancies, vacancy_skills, task_runs RESTART IDENTITY CASCADE"
            )
        )
        session.commit()


@pytest.fixture
def redis_client():
    r = redis_lib.from_url(
        settings.REDIS_URL.replace("redis://redis:", "redis://localhost:")
    )
    yield r
    r.flushdb()
