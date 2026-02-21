# Дорожная карта JobPilot

## Step 1.1 — Базовая инфраструктура ✓

Реализовано:
- FastAPI app factory (`app/main.py`)
- Config с pydantic-settings (`app/config.py`)
- Database setup: async engine (FastAPI) + sync engine (Celery) (`app/database.py`)
- Health endpoint (`GET /health` — статус PostgreSQL и Redis)
- Celery конфигурация (`app/tasks/celery_app.py`)
- Docker Compose (api, worker, beat, db, redis)
- Unit + integration тесты

## Step 1.2 — SQLAlchemy модели + Alembic миграции

- SQLAlchemy модели: `Vacancy`, `VacancySkill`, `TaskRun`
- Alembic init + первая миграция
- Upsert логика с триггером updated_at
- Integration тесты с реальной БД

**В начале этого шага:**

Добавить `ruff` как dev-зависимость:
```bash
uv add --dev ruff
```

Настройка в `pyproject.toml`:
```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I"]  # pycodestyle + pyflakes + isort
```

## Step 1.3 — Fetcher + Enricher workers

- hh.ru API client (поиск + детали вакансии)
- Redis dedup (SET NX EX 35 дней)
- Celery задачи: fetch_vacancies, enrich_vacancies (батч до 20)
- Парсинг навыков, расчёт relevance_score
- Integration тесты с живыми сервисами

**В начале этого шага:**

Создать проектный скилл `jobpilot-testing` (`.claude/skills/jobpilot-testing/SKILL.md`)
с соглашениями по тестам: структура unit/integration, что мокировать,
pytest fixtures-конвенции, как запускать тесты с Docker.

## Step 1.4 — REST API

- `GET /vacancies` — список вакансий с фильтрацией и пагинацией
- `POST /tasks/fetch` — запуск задачи сбора
- `GET /tasks/{id}` — статус задачи
- Pydantic схемы ответов
- Unit тесты endpoint-ов

## Step 1.5 — Rate limiting, circuit breaker

- Rate limiting для hh.ru API (не более X запросов в секунду)
- Circuit breaker при недоступности hh.ru
- Retry с экспоненциальным backoff
- Метрики и логирование

---

## Отложенные решения

### CI/CD — после Step 1.3 (первые реальные интеграционные тесты)

Делать CI/CD имеет смысл, когда появятся тесты с живой БД (после Step 1.2
с Alembic-миграциями или Step 1.3 с парсером).

Минимальный pipeline (GitHub Actions):
- `uv run ruff check .` — линтинг
- `uv run pytest tests/unit/` — unit-тесты (без Docker)
- `docker compose up -d && uv run pytest tests/integration/` — интеграционные
  (с сервисами через `services:` в workflow)
