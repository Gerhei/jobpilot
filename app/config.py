from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    DATABASE_URL: str          # postgresql+asyncpg://... (FastAPI async)
    DATABASE_URL_SYNC: str     # postgresql+psycopg2://... (Celery sync)

    # Redis
    REDIS_URL: str             # redis://redis:6379/0

    # hh.ru API
    HH_API_BASE_URL: str = "https://api.hh.ru"
    HH_SEARCH_KEYWORDS: str
    HH_AREA_ID: int = 1        # 1 = Москва
    HH_SALARY_FROM: int = 0
    HH_SALARY_TO: int = 0      # 0 = без ограничения

    # Нормализация валют (фиксированный курс)
    # TODO использовать API для определения курса
    USD_TO_RUB: float = 90.0
    EUR_TO_RUB: float = 100.0
    KZT_TO_RUB: float = 0.21

    # Эталонный стек для скора
    REFERENCE_SKILLS: str = "python,fastapi,postgresql,redis,celery,docker"

    # Circuit breaker
    CIRCUIT_BREAKER_THRESHOLD: int = 5   # N подряд failures → circuit open
    CIRCUIT_BREAKER_TIMEOUT: int = 3600  # секунды (1 час)

    # Rate limit для POST /tasks/fetch
    FETCH_RATE_LIMIT_SECONDS: int = 300  # 5 минут

    @property
    def reference_skills_set(self) -> set[str]:
        return {s.strip().lower() for s in self.REFERENCE_SKILLS.split(",") if s.strip()}


settings = Settings()
