---
name: jobpilot-testing
description: Соглашения по тестированию JobPilot — структура, что мокировать,
  fixtures-конвенции, запуск с Docker.
---

# Тестирование JobPilot

## Структура

tests/
  unit/         # Без внешних зависимостей
  integration/  # Требуют Docker (db + redis)

## Unit-тесты

- Нет реальных БД, Redis, HTTP
- Тестировать: чистые функции (enrichment, skills_map, currency)
- Мокировать: httpx.Client → unittest.mock.MagicMock
- Мокировать: redis.Redis → unittest.mock.MagicMock
- Мокировать: SQLAlchemy Session → unittest.mock.MagicMock

```bash
uv run pytest tests/unit/ -v   # без Docker
```

## Integration-тесты

- Реальные сервисы: PostgreSQL + Redis через Docker
- hh.ru HTTP → мокировать (нет зависимости от внешних API)
- Fixtures в tests/integration/conftest.py

```bash
docker compose up -d db redis
uv run pytest tests/integration/ -v
docker compose down
```

## Fixtures-конвенции

Sync DB fixture (для Celery-слоя):
```python
@pytest.fixture
def db_session():
    from app.database import SyncSessionLocal
    with SyncSessionLocal() as session:
        yield session
        session.rollback()
```

Redis fixture:
```python
@pytest.fixture
def redis_client():
    import redis
    from app.config import settings
    r = redis.from_url(settings.REDIS_URL.replace("redis", "redis"))
    yield r
    r.flushdb()
```

## Качество кода (перед каждым коммитом)

```bash
uv run ruff check . --fix && uv run ruff format . && uv run pytest tests/ -v
```
