# JobPilot

Агрегатор вакансий с hh.ru для Python-разработчиков.
Автоматически собирает вакансии, нормализует навыки, считает релевантность
относительно вашего стека и хранит всё в PostgreSQL.

## Что делает

- **Собирает** вакансии с hh.ru каждый час через Celery Beat
- **Обогащает** каждую вакансию: определяет грейд (junior/middle/senior/lead),
  формат работы (remote/office/hybrid), нормализует навыки
- **Конвертирует** зарплату в рубли (USD, EUR, KZT → RUB)
- **Ранжирует** по релевантности: `score = совпавшие навыки / эталонный стек`
- **Дедуплицирует** через Redis — одна вакансия не загружается дважды за 35 дней
- **Защищает** от недоступности hh.ru через circuit breaker

## Стек

| Компонент | Технология |
|-----------|-----------|
| API | FastAPI 0.129 + uvicorn |
| Фоновые задачи | Celery 5.6 + Celery Beat |
| Брокер / кэш | Redis 7 |
| База данных | PostgreSQL 16 + SQLAlchemy 2 |
| HTTP-клиент | httpx (sync, для Celery) |
| Миграции | Alembic |
| Конфигурация | pydantic-settings |
| Тесты | pytest + pytest-asyncio |
| Линтер | ruff |
| Инфраструктура | Docker Compose |
| Python | 3.12 + uv |

## Быстрый старт

```bash
git clone <repo>
cd jobpilot

cp .env.example .env
# Отредактируйте .env — минимум нужно задать HH_SEARCH_KEYWORDS

docker compose up
```

Сервисы поднимутся автоматически. Celery Beat запустит первый сбор вакансий
через час. Для немедленного запуска:

```bash
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.fetch.fetch_vacancies
```

## Конфигурация

Все параметры — в `.env` (см. `.env.example`):

| Переменная | По умолчанию | Описание |
|-----------|-------------|---------|
| `HH_SEARCH_KEYWORDS` | — | Поисковый запрос на hh.ru |
| `HH_AREA_ID` | `1` | Регион (1 = Москва) |
| `REFERENCE_SKILLS` | `python,fastapi,...` | Эталонный стек для скора |
| `USD_TO_RUB` | `90.0` | Курс доллара |
| `EUR_TO_RUB` | `100.0` | Курс евро |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Кол-во ошибок до открытия circuit breaker |
| `CIRCUIT_BREAKER_TIMEOUT` | `3600` | Время паузы при открытом circuit (сек) |

## Как работает

### Поток данных

```
Celery Beat (каждый час)
    │
    ▼
fetch_vacancies
    ├─ Проверить circuit breaker (Redis) → если открыт: пропустить
    ├─ Создать запись TaskRun (status=running)
    ├─ Постранично обойти hh.ru API
    │   ├─ is_new? (Redis SET NX) → если нет: пропустить
    │   └─ Загрузить детали вакансии
    └─ Отправить батч (до 20) → enrich_batch
            │
            ▼
        enrich_batch
            ├─ extract_skills()        навыки из key_skills или description
            ├─ calc_relevance_score()  пересечение с REFERENCE_SKILLS
            ├─ extract_grade()         junior / middle / senior / lead
            ├─ extract_work_format()   remote / office / hybrid
            ├─ to_rub()                конвертация зарплаты
            └─ upsert → vacancies + vacancy_skills
```

### Нормализация навыков

Словарь из ~40 алиасов приводит сырые названия к каноническим:

| Как пишут в вакансии | Канонический вид |
|----------------------|-----------------|
| питон, python3, py | python |
| postgres, psql, pg | postgresql |
| docker-compose | docker |
| k8s, кубернетес | kubernetes |
| drf, django rest | django |

### Релевантность

```
score = len(vacancy_skills ∩ reference_skills) / len(reference_skills)
```

- `NULL` — навыки вообще не найдены (нет данных для оценки)
- `0.0` — навыки найдены, но не совпали с вашим стеком
- `0.67` — две трети вашего стека присутствуют в вакансии
- `1.0` — полное совпадение

### Дедупликация

```
Redis: SET seen:hh:{vacancy_id} 1 NX EX 2592000
```

Атомарная операция без race conditions. Вакансия не будет повторно
обработана в течение 35 дней — даже при параллельных воркерах.

### Circuit Breaker

При 5 подряд ошибках запросов к hh.ru:
- Открывается circuit на 1 час (настраивается)
- Следующие запуски `fetch_vacancies` пропускаются
- После истечения таймаута: попытка возобновить работу

## API

После `docker compose up` доступно на `http://localhost:8000`:

| Endpoint | Описание |
|----------|---------|
| `GET /health` | Статус PostgreSQL и Redis |

Планируется (Step 1.4):

| Endpoint | Описание |
|----------|---------|
| `GET /vacancies` | Список вакансий с фильтрацией по грейду, формату, скору |
| `POST /tasks/fetch` | Ручной запуск сбора вакансий |
| `GET /tasks/{id}` | Статус задачи сбора |

## Структура БД

```
vacancies
  id, external_id, source        — идентификация
  title, company, description    — основные данные
  salary_from, salary_to         — оригинальные значения
  salary_from_rub, salary_to_rub — конвертированные в рубли
  currency, grade, work_format   — обогащение
  relevance_score                — NULL | 0.0..1.0
  published_at, updated_at       — временны́е метки
  description_tsv                — FTS-вектор (триггер)

vacancy_skills
  vacancy_id → vacancies.id
  skill (нормализованное название)

task_runs
  task_name, status              — running / success / failure
  started_at, finished_at
  vacancies_fetched, error
```

## Тестирование

```bash
# Unit-тесты (без Docker, ~0.2 сек):
uv run pytest tests/unit/ -v

# Integration-тесты (нужен Docker):
docker compose up -d db redis
DATABASE_URL="postgresql+asyncpg://jobpilot:jobpilot@localhost:5432/jobpilot" \
DATABASE_URL_SYNC="postgresql+psycopg2://jobpilot:jobpilot@localhost:5432/jobpilot" \
REDIS_URL="redis://localhost:6379/0" \
HH_SEARCH_KEYWORDS="python developer" \
uv run pytest tests/integration/ -v
docker compose down
```

Текущее покрытие: **37 тестов** (30 unit + 7 integration).
