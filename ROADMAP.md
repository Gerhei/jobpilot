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

## Step 1.2 — SQLAlchemy модели + Alembic миграции ✓

- SQLAlchemy модели: `Vacancy`, `VacancySkill`, `TaskRun`
- Alembic init + первая миграция
- Upsert логика с триггером updated_at
- Integration тесты с реальной БД

## Step 1.3 — Fetcher + Enricher workers ✓

- hh.ru API client (поиск + детали вакансии)
- Redis dedup (SET NX EX 35 дней)
- Celery задачи: fetch_vacancies, enrich_vacancies (батч до 20)
- Парсинг навыков, расчёт relevance_score
- Integration тесты с живыми сервисами

## Step 1.4 — REST API ✓

- `GET /api/v1/vacancies` — список с фильтрами и пагинацией
- `POST /api/v1/tasks/fetch` — fire-and-forget запуск сбора (202 Accepted)
- `GET /api/v1/tasks/{id}` — статус TaskRun
- Чистая архитектура: Router → UseCase → Repository
- 17 новых unit-тестов (47 всего)

## Step 1.5 — Защита от бана и ограничения парсинга

Проблемы, выявленные на Step 1.4:
- hh.ru возвращает 403 на ~30% вакансий при анонимных запросах
- Парсинг 2000 вакансий занимает ~5 минут — риск бана при частых запусках

Что делать:
- Настраиваемый лимит парсинга: `MAX_VACANCIES_PER_RUN` (например, 200)
  и/или `MAX_PAGES_PER_RUN` — задача прекращает обход после достижения лимита
- OAuth-авторизация hh.ru: access token снимает большинство 403
  (токен приложения, не пользователя — для анонимного сбора)
- Rate limiting для `POST /tasks/fetch`: не чаще раза в N минут
  (config `FETCH_RATE_LIMIT_SECONDS` уже есть, нужно подключить)

## Step 1.6 — Параметризованный поиск через API

Сейчас критерии поиска хардкодятся в `.env` (`HH_SEARCH_KEYWORDS`, `HH_AREA_ID`).
Это неудобно: нельзя поменять поиск без перезапуска сервиса.

Варианты (обсудить перед реализацией):
- `POST /tasks/fetch` принимает тело `{"keywords": "python fastapi", "area": 1}`
  — разовый поиск с произвольными параметрами
- Таблица `SearchProfile` — именованные профили поиска, задача ссылается на профиль
- Гибрид: тело опционально, fallback на `.env` если не передано

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
