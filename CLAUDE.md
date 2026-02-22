# JobPilot — инструкция для Claude Code

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
  services/
    skills_map.py  # SKILLS_MAP + normalize_skill()
    currency.py    # to_rub() с фиксированными курсами
    enrichment.py  # extract_skills, calc_relevance_score, extract_grade, extract_work_format
    hh_client.py   # sync httpx.Client с retry и 429-handling
    dedup.py       # DedupService — Redis NX EX + circuit breaker
  tasks/
    celery_app.py  # Celery config + beat_schedule
    fetch.py       # fetch_vacancies — обход hh.ru, дедупликация, батчи
    enrich.py      # enrich_batch — upsert в PostgreSQL + навыки
    cleanup.py     # cleanup_old_vacancies — удаление старше 30 дней
  config.py        # Settings (pydantic-settings)
  database.py      # async engine (FastAPI) + sync engine (Celery)
  main.py          # Фабрика FastAPI приложения
tests/
  unit/            # Без внешних зависимостей (30 тестов)
  integration/     # С реальными сервисами Docker (7 тестов)
migrations/        # Alembic
.claude/skills/    # AI-правила проекта
```

## Бизнес-логика

### Поток данных

```
Beat (каждый час)
  → fetch_vacancies (Celery task)
      → HHClient.search_vacancies() — постраничный обход
      → DedupService.is_new() — пропустить уже виденные (Redis SET NX EX 35д)
      → HHClient.get_vacancy() — детали вакансии
      → enrich_batch.delay([...]) — батч до 20 вакансий
          → extract_skills() — из key_skills или regex по description
          → calc_relevance_score() — пересечение с REFERENCE_SKILLS
          → extract_grade() — junior/middle/senior/lead
          → extract_work_format() — remote/office/hybrid
          → to_rub() — конвертация зарплаты
          → pg_insert().on_conflict_do_update() — upsert в vacancies
          → pg_insert().on_conflict_do_nothing() — навыки в vacancy_skills
```

### Нормализация навыков

`skills_map.py` содержит ~40 алиасов → канонические названия:
- "питон", "python3", "py" → "python"
- "postgres", "psql", "pg" → "postgresql"
- "docker-compose", "docker compose" → "docker"
- и т.д.

Навыки берутся из `key_skills` вакансии (если есть), иначе regex по `description`.

### Релевантность

`relevance_score = len(vacancy_skills ∩ reference_skills) / len(reference_skills)`

- `NULL` — навыки не найдены (нет данных)
- `0.0` — навыки найдены, но не совпали с эталоном
- `1.0` — полное совпадение

Эталонный стек задаётся в `.env`: `REFERENCE_SKILLS=python,fastapi,postgresql,...`

### Дедупликация

`Redis SET seen:hh:{id} 1 NX EX 2592000` (35 дней) — атомарно, без race conditions.
Одна и та же вакансия не будет повторно запрошена в течение 35 дней.

### Circuit Breaker

Если hh.ru недоступен N раз подряд (`CIRCUIT_BREAKER_THRESHOLD=5`) — открывается
circuit breaker на `CIRCUIT_BREAKER_TIMEOUT=3600` секунд. Следующий `fetch_vacancies`
увидит открытый circuit и пропустит выполнение (`"status": "skipped"`).

### Upsert + updated_at

При повторном обходе одной вакансии:
- Если `description`, `salary_from`, `salary_to` не изменились → `updated_at` не трогается
- Если изменились → `updated_at = NOW()`

Реализовано через `SQLAlchemy case() + is_distinct_from()`.

## Тестирование

```bash
uv run pytest tests/unit/ -v           # unit (без Docker)
docker compose up -d db redis
DATABASE_URL="postgresql+asyncpg://jobpilot:jobpilot@localhost:5432/jobpilot" \
DATABASE_URL_SYNC="postgresql+psycopg2://jobpilot:jobpilot@localhost:5432/jobpilot" \
REDIS_URL="redis://localhost:6379/0" \
HH_SEARCH_KEYWORDS="python developer" \
uv run pytest tests/integration/ -v
docker compose down
```

Качество кода (перед каждым коммитом):
```bash
uv run ruff check . --fix && uv run ruff format . && uv run pytest tests/unit/ -v
```

## Архитектурные решения

- **Async FastAPI + Sync Celery**: явное разделение — FastAPI использует asyncpg,
  Celery использует psycopg2 (избегаем asyncio.run в воркерах)
- **Redis dedup**: SET NX EX 35 дней — атомарно, без race conditions
- **Batch enrichment**: до 20 вакансий за задачу Celery
- **NULL relevance_score**: NULL = скиллы не найдены (vs 0.0 = найдены, но не совпали)
- **Upsert с умным updated_at**: обновляет только при реальных изменениях данных
- **FTS-триггер в PostgreSQL**: `description_tsv` обновляется триггером на INSERT/UPDATE

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

Специфичные для JobPilot правила:

- **task-workflow** — управление задачами через todo.md, один баг за раз, чекпоинты
- **commit-conventions** — структура коммитов, язык коммитов: **русский**
- **jobpilot-testing** — соглашения по тестам: структура unit/integration,
  что мокировать, fixtures-конвенции, запуск с Docker

Claude вызывает эти скиллы автоматически при старте задачи и при создании коммита.

Для установки скиллов в свой Claude Code:
```bash
cp -r .claude/skills/* ~/.claude/skills/
```

## Дорожная карта

См. [ROADMAP.md](ROADMAP.md)

## Текущий статус: Step 1.3 завершён

Реализовано: сервисы нормализации, HH-клиент, дедупликация, Celery-задачи
(fetch/enrich/cleanup), beat schedule, 37 тестов (30 unit + 7 integration).
Следующий шаг: Step 1.4 — REST API (GET /vacancies, POST /tasks/fetch).
