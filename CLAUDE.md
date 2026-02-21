# JobPilot

Агрегатор вакансий с hh.ru с автоматическим обогащением и ранжированием.
Собирает вакансии по Python-разработчикам, нормализует навыки, считает релевантность.

## Стек

| Компонент | Технология |
|-----------|-----------|
| API | FastAPI 0.129 + uvicorn |
| Фоновые задачи | Celery 5.6 + Celery Beat |
| Брокер / кэш | Redis 7 |
| База данных | PostgreSQL 16 + SQLAlchemy 2 |
| Миграции | Alembic |
| Конфигурация | pydantic-settings |
| Тесты | pytest + pytest-asyncio |
| Инфраструктура | Docker Compose (5 сервисов) |
| Python | 3.12, пакетный менеджер uv |

## Запуск

```bash
cp .env.example .env   # заполнить переменные
docker compose up      # поднимает api, worker, beat, db, redis
```

## Переменные окружения

Обязательные (см. `.env.example`):
- `DATABASE_URL` — postgresql+asyncpg://... (FastAPI)
- `DATABASE_URL_SYNC` — postgresql+psycopg2://... (Celery)
- `REDIS_URL` — redis://redis:6379/0
- `HH_SEARCH_KEYWORDS` — ключевые слова для поиска (через запятую)
- `REFERENCE_SKILLS` — эталонный стек для расчёта релевантности

## Структура проекта

```
app/
  api/v1/          # REST endpoints (GET /vacancies, POST /tasks/fetch)
  api/health.py    # GET /health — статус PostgreSQL и Redis
  models/          # SQLAlchemy модели (Vacancy, VacancySkill, TaskRun)
  schemas/         # Pydantic схемы
  services/        # Бизнес-логика
  tasks/
    celery_app.py  # Конфигурация Celery
  config.py        # Settings (pydantic-settings)
  database.py      # async engine (FastAPI) + sync engine (Celery)
  main.py          # Фабрика FastAPI приложения
tests/
  unit/            # Без внешних зависимостей
  integration/     # С реальными сервисами (Docker)
migrations/        # Alembic
.claude/skills/    # AI-правила проекта (task-workflow, commit-conventions)
```

## Тестирование

```bash
uv run pytest tests/unit/ -v           # unit (без Docker)
docker compose up -d
uv run pytest tests/integration/ -v   # интеграционные
```

Качество кода (запускать перед каждым коммитом):
```bash
uv run ruff check . --fix && uv run ruff format . && uv run pytest tests/ -v
```

## Архитектурные решения

- **Async FastAPI + Sync Celery**: явное разделение — FastAPI использует asyncpg,
  Celery использует psycopg2 (избегаем asyncio.run в воркерах)
- **Redis dedup**: SET NX EX 35 дней — атомарно, без race conditions
- **Batch enrichment**: до 20 вакансий за задачу Celery
- **NULL relevance_score**: NULL = скиллы не найдены (vs 0.0 = найдены, но не совпали)
- **Upsert с триггером**: обновляет updated_at только при реальных изменениях данных

## AI-правила проекта

Проект ведётся с помощью Claude Code. Используется два уровня скиллов:

### Superpowers (официальные, ~/.claude/plugins/)

14 скиллов профессионального AI-воркфлоу, активны автоматически:
- **brainstorming** — перед любой творческой работой и созданием фич
- **writing-plans** — перед многошаговыми задачами
- **test-driven-development** — перед написанием любого кода
- **systematic-debugging** — при ошибках и упавших тестах
- **verification-before-completion** — перед заявлением что что-то готово
- **executing-plans / subagent-driven-development** — при выполнении планов
- и другие (requesting-code-review, finishing-a-development-branch, ...)

### Проектные скиллы (.claude/skills/)

Специфичные для JobPilot правила — в `.claude/skills/`:

- **task-workflow** — управление задачами через todo.md, один баг за раз, чекпоинты
- **commit-conventions** — структура коммитов, язык коммитов: **русский**
- **jobpilot-testing** — соглашения по тестам (планируется, см. ROADMAP.md)

Claude вызывает эти скиллы автоматически при старте задачи и при создании коммита.

Для установки скиллов в свой Claude Code:
```bash
cp -r .claude/skills/* ~/.claude/skills/
```

## Дорожная карта

См. [ROADMAP.md](ROADMAP.md)

## Текущий статус: Step 1.1 завершён

Реализовано: FastAPI app factory, config, database setup, health endpoint,
Celery config, Docker Compose, unit + integration tests.
Следующий шаг: Step 1.2 — SQLAlchemy модели + Alembic миграции.
