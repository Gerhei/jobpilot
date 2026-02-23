from app.models.vacancy import Vacancy, VacancySkill  # noqa: F401
from app.services.dedup import DedupService
from app.tasks.enrich import enrich_batch

# Реалистичный ответ hh.ru
SAMPLE_VACANCY = {
    "id": "999001",
    "name": "Senior Python Developer",
    "employer": {"name": "Acme Corp"},
    "description": "Ищем Senior Python разработчика. Удалённая работа.",
    "key_skills": [{"name": "Python"}, {"name": "FastAPI"}, {"name": "PostgreSQL"}],
    "salary": {"from": 200000, "to": 300000, "currency": "RUR"},
    "alternate_url": "https://hh.ru/vacancy/999001",
    "published_at": "2026-02-20T10:00:00+0300",
}


def test_enrich_batch_saves_vacancy(db_session):
    """enrich_batch сохраняет вакансию и навыки в реальную БД."""
    enrich_batch([SAMPLE_VACANCY])

    from app.database import SyncSessionLocal

    with SyncSessionLocal() as s:
        v = s.query(Vacancy).filter_by(external_id="999001", source="hh").first()
        assert v is not None
        assert v.title == "Senior Python Developer"
        assert v.salary_from_rub == 200000
        assert v.relevance_score is not None
        skills = {sk.skill for sk in v.skills}
        assert "python" in skills


def test_enrich_batch_upsert_idempotent(db_session):
    """Повторный upsert без изменений не трогает updated_at."""
    enrich_batch([SAMPLE_VACANCY])

    from app.database import SyncSessionLocal

    with SyncSessionLocal() as s:
        v1 = s.query(Vacancy).filter_by(external_id="999001").first()
        updated_at_before = v1.updated_at

    enrich_batch([SAMPLE_VACANCY])  # повторно те же данные

    with SyncSessionLocal() as s:
        v2 = s.query(Vacancy).filter_by(external_id="999001").first()
        assert v2.updated_at == updated_at_before  # не изменился


def test_enrich_batch_null_score_if_no_skills(db_session):
    """relevance_score = NULL если навыки не распознаны."""
    unknown_vacancy = {
        **SAMPLE_VACANCY,
        "id": "999002",
        "key_skills": [],
        "description": "Требования не указаны",
    }
    enrich_batch([unknown_vacancy])

    from app.database import SyncSessionLocal

    with SyncSessionLocal() as s:
        v = s.query(Vacancy).filter_by(external_id="999002").first()
        assert v.relevance_score is None


def test_dedup_prevents_duplicate(redis_client):
    """is_new() возвращает True первый раз, False при повторе."""
    svc = DedupService(redis_client)
    assert svc.is_new("hh", "dedup-test-id") is True
    assert svc.is_new("hh", "dedup-test-id") is False
