from app.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/test")
    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql+psycopg2://u:p@localhost/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("HH_API_BASE_URL", "https://api.hh.ru")
    monkeypatch.setenv("HH_SEARCH_KEYWORDS", "python developer")
    monkeypatch.setenv("HH_AREA_ID", "1")
    monkeypatch.setenv("REFERENCE_SKILLS", "python,fastapi,postgresql")

    settings = Settings()

    assert settings.DATABASE_URL == "postgresql+asyncpg://u:p@localhost/test"
    assert settings.REDIS_URL == "redis://localhost:6379/0"
    assert settings.HH_AREA_ID == 1
    assert "python" in settings.reference_skills_set


def test_reference_skills_parsed_as_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/test")
    monkeypatch.setenv("DATABASE_URL_SYNC", "postgresql+psycopg2://u:p@localhost/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("HH_API_BASE_URL", "https://api.hh.ru")
    monkeypatch.setenv("HH_SEARCH_KEYWORDS", "python developer")
    monkeypatch.setenv("HH_AREA_ID", "1")
    monkeypatch.setenv("REFERENCE_SKILLS", "python , fastapi , postgresql")

    settings = Settings()

    assert settings.reference_skills_set == {"python", "fastapi", "postgresql"}
