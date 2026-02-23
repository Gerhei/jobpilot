# ТЗ: Job Vacancy Pipeline
**Версия:** 3.1  
**Автор:** And  
**Дата:** Февраль 2026  
**Тип проекта:** Портфолио + практический инструмент

> **Changelog v3.0:** Исправлена Redis-дедупликация (SET NX EX вместо SADD); UNIQUE constraint переведён на (external_id, source); upsert обновлён соответственно; published_at → NOT NULL; relevance_score = NULL при пустом стеке; trigger обновляет updated_at только при реальном изменении данных; добавлена стратегия ошибок hh.ru API (circuit breaker); стандартизированы error responses; добавлен rate limit на POST /tasks/fetch; уточнена логика фильтрации по skills (AND/OR); описана стратегия total_approx; FTS взвешен по title/description; здоровье API вынесено в корень; cursor-пагинация явно отнесена в Phase 2, Phase 1 использует offset; выбран plainto_tsquery для пользовательского ввода.

---

## 1. Постановка проблемы

### Контекст
Python backend-разработчик ведёт активный поиск работы. За время поиска подано ~150 заявок через hh.ru, конверсия в HR-диалог составляет 2–3%. Основные гипотезы о причинах низкой конверсии:

- Ручная фильтрация вакансий занимает много времени → заявки отправляются без глубокого анализа релевантности
- Нет систематического отслеживания обновлений вакансий
- Нет инструмента для оценки соответствия резюме требованиям конкретной вакансии
- hh.ru — единственная используемая площадка

### Проблема (формализованная)
Нет автоматизированного инструмента, который:
1. Агрегирует вакансии по заданным критериям в фоновом режиме
2. Обогащает и нормализует данные для сравнения
3. Предоставляет структурированный API для анализа и фильтрации
4. Масштабируется на несколько источников

### Цели проекта
**Практическая цель:** Ускорить и улучшить качество отбора вакансий за счёт автоматизации сбора и обогащения данных.

**Портфолио-цель:** Демонстрация навыков проектирования распределённых систем, работы с очередями задач, оптимизации БД и построения REST API — в одном связном проекте с реальным use case.

---

## 2. Функциональные требования

### FR-1: Сбор вакансий
- Система периодически опрашивает API hh.ru по заданным параметрам (ключевые слова, регион, зарплатный диапазон), конфигурируются через `.env`
- Поисковый `GET /vacancies` возвращает усечённые данные; для каждой новой вакансии делается отдельный `GET /vacancies/{id}` — батчами по 20 с задержкой между запросами
- Пагинация обходится с соблюдением rate limits и обработкой ошибок (см. FR-6)

### FR-2: Дедупликация (атомарная, с TTL)
Реализована через строковые ключи Redis с NX-флагом:

```
SET seen:{source}:{external_id} 1 NX EX 3024000
```

- `NX` — операция атомарна: ключ либо создаётся (новая вакансия → возвращает OK), либо уже существует (дубль → возвращает nil)
- `EX 3024000` — TTL 35 дней (35 × 86400); автоочистка без дополнительных задач; TTL превышает срок хранения вакансий в БД (30 дней)
- Race condition исключён: одна атомарная операция вместо `SISMEMBER` + `SADD`
- Ключ включает `source`, чтобы не пересекаться с другими источниками

### FR-3: Обогащение данных (батчами)
- Fetcher публикует батчи новых вакансий (до 20 штук) задачей `enrich_batch` — не по одной задаче на вакансию

#### FR-3.1: Извлечение навыков (источники и приоритеты)

hh.ru API в ответе `GET /vacancies/{id}` возвращает поле `key_skills: [{"name": "Python"}, ...]`. Это структурированные данные от работодателя, их используем в первую очередь.

Но `key_skills` часто пуст — работодатель не заполнил теги, все требования только в `description`. Поэтому пайплайн двухуровневый:

**Источник 1 — `key_skills` (приоритетный):**
```python
raw_skills = [s["name"] for s in vacancy_data.get("key_skills", [])]
```

**Источник 2 — `description` (fallback, если `key_skills` пуст):**
Ищем вхождения всех ключей `SKILLS_MAP` в тексте описания. Поиск регистронезависимый, по границам слов (`\b`), чтобы не матчить "python" внутри "monopython":
```python
if not raw_skills:
    description = vacancy_data.get("description", "")
    raw_skills = [
        key for key in SKILLS_MAP
        if re.search(rf"\b{re.escape(key)}\b", description, re.IGNORECASE)
    ]
```

После извлечения из любого источника — нормализация через `normalize_skill()`:
```python
normalized = {normalize_skill(s) for s in raw_skills}
```

**Почему не парсим description всегда (даже при наличии key_skills):** `key_skills` — явный сигнал от работодателя, description может содержать навыки в негативном контексте ("опыт с X не требуется") или в разделе про компанию. Смешивать источники без весов даёт шум.

**`relevance_score = NULL`** если `normalized` пуст после обоих этапов — нет данных о навыках, не нулевое совпадение.

#### FR-3.2: Остальное обогащение
- **Нормализация зарплаты:** к рублям по фиксированному курсу из конфига; вакансии без валюты или с неизвестной валютой → `salary_from_rub = NULL`
- **Скор релевантности:** `len(normalized & reference_skills) / len(reference_skills)`, где `reference_skills` — эталонный список из конфига
- **Извлечение грейда и формата:** regex по заголовку и описанию
- **Upsert:** если `(external_id, source)` уже в БД — обновляются `salary_from/to`, `description`, `relevance_score`; `updated_at` обновляется **только** при реальном изменении данных (см. раздел 3.4)

### FR-4: REST API
Все эндпоинты под префиксом `/api/v1/`. Health-check — в корне `/health` (без версии: load balancer'ы и Docker healthcheck'и должны иметь к нему доступ без знания версии API).

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | Статус сервиса (PostgreSQL, Redis) |
| GET | `/api/v1/vacancies` | Список вакансий с фильтрами и пагинацией |
| GET | `/api/v1/vacancies/{id}` | Карточка вакансии |
| POST | `/api/v1/tasks/fetch` | Ручной запуск сбора (rate-limited) |
| GET | `/api/v1/tasks` | История задач |

### FR-5: Фильтрация вакансий — логика skills

`GET /api/v1/vacancies?skills=python,fastapi,postgresql`

**AND-логика** (вакансия должна содержать **все** указанные навыки):

```sql
SELECT v.* FROM vacancies v
WHERE v.id IN (
  SELECT vacancy_id FROM vacancy_skills
  WHERE skill = ANY(ARRAY['python', 'fastapi', 'postgresql'])
  GROUP BY vacancy_id
  HAVING COUNT(DISTINCT skill) = 3   -- количество переданных навыков
)
```

AND-логика выбрана как более полезная для пользователя: ищешь позицию с конкретным стеком, а не вакансии где встречается хоть что-то из списка. Может быть расширена параметром `skills_mode=or` в Phase 3.

### FR-6: Обработка ошибок hh.ru API
| Ситуация | Поведение |
|---|---|
| 429 Too Many Requests | Ждём значение из заголовка `Retry-After`, fallback — 60 секунд |
| 5xx / сетевая ошибка | Retry: 3 попытки с exponential backoff (2¹, 2², 2³ секунд) |
| 403 Forbidden | Задача помечается как `failure`, запись в `task_runs.error`, задача не ретраится |
| Невалидный JSON | Логируется с payload, задача помечается `failure` |
| Нет данных / пустой результат | Нормальное завершение (`success`), `vacancies_fetched = 0` |

После N подряд идущих `failure` (конфигурируется, по умолчанию 5) — Celery Beat временно приостанавливает расписание на 1 час (circuit breaker через Redis-флаг `circuit_open`). FastAPI `/health` отражает состояние circuit breaker.

### FR-7: Мониторинг задач
- Статусы: `pending → running → success / failure`
- Retry: 3 попытки с exponential backoff
- `task_runs` хранит `vacancies_fetched` и `vacancies_saved` как явные колонки

### FR-8: Очистка устаревших данных
- Celery-задача `cleanup_old_vacancies`, запускается раз в сутки через Beat
- Удаляет вакансии с `published_at < NOW() - INTERVAL '30 days'`
- Redis TTL (35 дней) обеспечивает автоочистку дедупликационных ключей

---

## 3. Нефункциональные требования

| Параметр | Требование |
|---|---|
| Время ответа API | < 300ms для списка вакансий |
| Хранение истории | Вакансии хранятся минимум 30 дней, затем удаляются |
| Отказоустойчивость | Retry 3 попытки, exponential backoff; circuit breaker при систематических сбоях |
| Воспроизводимость | `docker-compose up` без дополнительных шагов |
| Документация | OpenAPI/Swagger автогенерация через FastAPI |
| Версионирование API | Все бизнес-эндпоинты под `/api/v1/` |
| Error responses | Стандартизированный формат (см. раздел 3.6) |

---

## 4. Архитектура

### 4.1 Общий поток данных

```
┌─────────────────────────────────────────────────────────┐
│                        Клиент                           │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI (REST API)                          │
│  /health                                                 │
│  /api/v1/vacancies   /api/v1/vacancies/{id}             │
│  /api/v1/tasks/fetch /api/v1/tasks                      │
└──────┬──────────────────────────┬───────────────────────┘
       │ read                     │ trigger task
       ▼                          ▼
┌─────────────┐          ┌────────────────┐
│ PostgreSQL  │          │  Celery Beat   │  ← cron расписание
└──────▲──────┘          └───────┬────────┘
       │ write                   │ publish task
       │                         ▼
       │                ┌────────────────────────┐
       │                │  Redis                  │
       │                │  broker: Celery tasks   │
       │                │  dedup: seen:{s}:{id}   │
       │                │  circuit: circuit_open  │
       │                └───────┬────────────────┘
       │                        │ consume
       │          ┌─────────────▼──────────────────────┐
       │          │          Celery Workers              │
       │          │                                      │
       │          │  fetch_vacancies                     │
       │          │  → GET /vacancies (поиск, пагинация)│
       │          │  → SET seen:{s}:{id} NX EX          │
       │          │  → новые: GET /vacancies/{id}        │
       │          │  → батч → enrich_batch               │
       │          │                                      │
       │          │  enrich_batch                        │
       │          │  → нормализация стека/зарплаты       │
       │          │  → скор (NULL если нет навыков)      │
       │          │  → upsert ON CONFLICT (ext_id,src)  │
       │          │                                      │
       │          │  cleanup_old_vacancies (ежедневно)  │
       └──────────│  → DELETE WHERE published_at < -30d │
                  └─────────────────────────────────────┘
```

### 4.2 Celery + sync: явная стратегия

Celery workers синхронные по умолчанию. `asyncio.run()` внутри Celery-задачи — антипаттерн. Принятое решение: **синхронный `httpx.Client`** в задачах Fetcher и Enricher. FastAPI-слой остаётся async (`AsyncSession` SQLAlchemy, async endpoints). В Celery-слое используется синхронная `Session`.

Если в будущем потребуется async-native очередь (при добавлении нескольких источников с высоким throughput) — рассматривается **arq** или **taskiq** как замена Celery.

### 4.3 Схема базы данных

```sql
vacancies (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id       VARCHAR        NOT NULL,
  source            VARCHAR        NOT NULL DEFAULT 'hh',
  title             VARCHAR        NOT NULL,
  company           VARCHAR,
  description       TEXT,
  description_tsv   TSVECTOR,                -- обновляется триггером
  salary_from       INTEGER,                 -- оригинал
  salary_to         INTEGER,
  currency          VARCHAR(10),
  salary_from_rub   INTEGER,                 -- нормализованный к RUB
  salary_to_rub     INTEGER,
  grade             VARCHAR(20),             -- junior/middle/senior/lead
  work_format       VARCHAR(20),             -- remote/office/hybrid
  url               VARCHAR        NOT NULL,
  relevance_score   FLOAT,                   -- NULL = нет данных о навыках
  published_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  fetched_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_vacancy_source UNIQUE (external_id, source)
  -- UNIQUE(external_id, source), а не UNIQUE(external_id):
  -- числовые ID hh.ru и Habr могут совпадать
)

vacancy_skills (
  vacancy_id  UUID        NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
  skill       VARCHAR     NOT NULL,
  PRIMARY KEY (vacancy_id, skill)
)

task_runs (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  task_name         VARCHAR     NOT NULL,
  status            VARCHAR     NOT NULL,    -- pending/running/success/failure
  started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at       TIMESTAMPTZ,
  error             TEXT,
  vacancies_fetched INTEGER,                 -- пришло от API
  vacancies_saved   INTEGER,                 -- записано/обновлено в БД
  meta              JSONB                    -- параметры запроса, retry-count и т.д.
)
```

**Upsert учитывает source:**
```sql
INSERT INTO vacancies (...) VALUES (...)
ON CONFLICT (external_id, source) DO UPDATE SET
  salary_from    = EXCLUDED.salary_from,
  salary_to      = EXCLUDED.salary_to,
  description    = EXCLUDED.description,
  relevance_score = EXCLUDED.relevance_score,
  updated_at     = CASE
    WHEN vacancies.description IS DISTINCT FROM EXCLUDED.description
      OR vacancies.salary_from IS DISTINCT FROM EXCLUDED.salary_from
      OR vacancies.salary_to   IS DISTINCT FROM EXCLUDED.salary_to
    THEN NOW()
    ELSE vacancies.updated_at   -- данные не изменились → не трогаем
  END
```

### 4.4 Trigger: description_tsv с весами

Полнотекстовый поиск взвешен: заголовок важнее описания.

```sql
CREATE OR REPLACE FUNCTION update_vacancy_search() RETURNS TRIGGER AS $$
BEGIN
  NEW.description_tsv :=
    setweight(to_tsvector('russian', COALESCE(NEW.title, '')), 'A') ||
    setweight(to_tsvector('russian', COALESCE(NEW.description, '')), 'B');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER vacancy_search_update
  BEFORE INSERT OR UPDATE OF title, description ON vacancies
  FOR EACH ROW EXECUTE FUNCTION update_vacancy_search();
-- Триггер срабатывает только при изменении title или description,
-- а не при любом UPDATE — не перезаписывает updated_at без причины
```

### 4.5 Индексы

```sql
-- Фильтрация + сортировка по дате
CREATE INDEX idx_vacancies_published ON vacancies(published_at DESC) WHERE published_at IS NOT NULL;

-- Cursor-based пагинация (Phase 2): уникальная пара
CREATE INDEX idx_vacancies_cursor ON vacancies(published_at DESC, id DESC);

-- Полнотекстовый поиск (конфигурация 'russian' обязательна для морфологии)
CREATE INDEX idx_vacancies_fts ON vacancies USING GIN(description_tsv);

-- Скор + фильтры
CREATE INDEX idx_vacancies_score ON vacancies(relevance_score DESC NULLS LAST);
CREATE INDEX idx_vacancies_grade_format ON vacancies(grade, work_format, source);

-- Нормализованная зарплата
CREATE INDEX idx_vacancies_salary ON vacancies(salary_from_rub, salary_to_rub);

-- Поиск по навыкам (для AND-фильтра)
CREATE INDEX idx_vacancy_skills_skill ON vacancy_skills(skill);

-- Upsert: покрывается UNIQUE constraint (external_id, source)
```

### 4.6 Словарь синонимов стека

Хранится в `app/services/skills_map.py` как Python-словарь (версионируется в git, легко ревьювить). При необходимости выносится в YAML без изменения кода.

```python
SKILLS_MAP: dict[str, str] = {
    "питон": "python", "python3": "python", "python 3": "python", "py": "python",
    "fast api": "fastapi", "fast_api": "fastapi",
    "postgres": "postgresql", "psql": "postgresql", "pg": "postgresql",
    "rabbit": "rabbitmq", "rabbit mq": "rabbitmq",
    "к8с": "kubernetes", "k8s": "kubernetes",
    # ...
}

def normalize_skill(raw: str) -> str:
    key = raw.strip().lower()
    return SKILLS_MAP.get(key, key)
```

Стратегия расширения: нераспознанные скиллы логируются как `WARN unknown_skill=<value>`. В Phase 3 — автоматический маппинг через LLM.

### 4.7 Стандарт error responses

Все ошибки возвращаются в едином формате:

```json
{
  "error": {
    "code": "VACANCY_NOT_FOUND",
    "message": "Vacancy with id=abc not found",
    "details": {}
  }
}
```

FastAPI exception handler переопределяет стандартный `{"detail": "..."}`.

---

## 5. Инструменты и обоснование

| Инструмент | Роль | Почему |
|---|---|---|
| **FastAPI** | REST API | Async, автогенерация OpenAPI, Pydantic-валидация |
| **Celery** | Очередь задач | Periodic tasks (Beat), retry, разные очереди. Синхронный режим явно — без конфликтов с asyncio |
| **Redis** | Broker + дедупликация + circuit breaker | Broker для Celery, атомарные `SET NX EX` для дедупликации, флаг `circuit_open` |
| **PostgreSQL** | Хранение данных | ACID, `tsvector` с поддержкой `russian`, `JSONB`, составные индексы, upsert |
| **SQLAlchemy + Alembic** | ORM + миграции | Production-стандарт |
| **Docker Compose** | Оркестрация | 5 сервисов с healthcheck'ами |
| **pytest** | Тесты | Unit + интеграционные; пишутся в MVP |
| **httpx (sync)** | HTTP-клиент в Celery | Синхронный — без asyncio в задачах |

**Kafka — почему нет:** избыточен для текущего объёма (несколько тысяч вакансий раз в несколько часов, один источник). Redis + Celery покрывают с запасом. Добавляется при нескольких источниках с разными throughput-требованиями.

---

## 6. Этапы реализации

### MVP (Phase 1) — ~20 часов
**Цель:** Работающий пайплайн + REST API с offset-пагинацией + базовые тесты

#### Шаг 1.1: Инфраструктура (3ч)
- `docker-compose.yml`: FastAPI, Celery worker, Celery Beat, Redis, PostgreSQL с healthcheck'ами
- `pydantic-settings` конфиг через `.env` (DB, Redis, hh.ru params, курсы валют, reference_skills)
- Структура проекта (см. раздел 7)
- `GET /health` — проверяет PostgreSQL (`SELECT 1`) и Redis (`PING`); возвращает 200 или 503; отражает состояние circuit breaker

#### Шаг 1.2: Модели и миграции (2ч)
- SQLAlchemy-модели: `Vacancy`, `VacancySkill`, `TaskRun`
- Alembic: миграция с trigger, индексами, UNIQUE(external_id, source)

#### Шаг 1.3: Fetcher Worker (4ч)
- Синхронный `httpx.Client`, пагинация, обработка 429/5xx/403/невалидный JSON
- Атомарная дедупликация: `SET seen:{source}:{external_id} 1 NX EX 3024000`
- Детализирующие запросы `GET /vacancies/{id}` батчами по 20 с задержкой
- Circuit breaker: счётчик последовательных ошибок в Redis, флаг `circuit_open`
- Публикация `enrich_batch` с батчем данных
- Логирование в `TaskRun`

#### Шаг 1.4: Enricher Worker (3ч)
- Нормализация стека через `SKILLS_MAP`
- Нормализация зарплаты к рублям
- Скор: `NULL` если нет распознанных навыков; формула с `len(intersection) / len(reference)`
- Upsert `ON CONFLICT (external_id, source)` с умным `updated_at`

#### Шаг 1.5: REST API (4ч)
- `GET /api/v1/vacancies` — фильтры + **offset/limit пагинация**; `skills`-фильтр по AND-логике
- `GET /api/v1/vacancies/{id}` — карточка со skills[]
- `POST /api/v1/tasks/fetch` — ручной запуск; **rate limit: 1 запрос в 5 минут** (через Redis с TTL)
- `GET /api/v1/tasks` — история TaskRun, offset/limit (таблица небольшая, offset оправдан)
- Стандартизированные error responses (exception handler)
- Retry конфигурация Celery: `max_retries=3`, `countdown=lambda x: 2**x`

#### Шаг 1.6: Cleanup + тесты (2.5ч)
- Celery-задача `cleanup_old_vacancies` в Beat (раз в сутки)
- Unit-тесты: `normalize_skill`, `calc_score` (включая NULL-случай), `extract_grade`, `normalize_salary`
- Smoke-тест: `GET /health` → 200

---

### Phase 2: Production-ready — ~6 часов
**Цель:** Полнотекстовый поиск, cursor-пагинация, полное тест-покрытие

#### Шаг 2.1: Cursor-based пагинация (2ч)
Offset медленно работает на больших смещениях. Cursor кодируется в base64 из пары `(published_at, id)`:

```
GET /api/v1/vacancies?cursor=<base64>&limit=20
```

Декодируется в `WHERE (published_at, id) < ($1, $2)` — опирается на индекс `idx_vacancies_cursor`.

**`total_approx`** в ответе: используем `pg_class.reltuples` как быстрое приближение общего числа вакансий. Точный `COUNT(*)` с учётом фильтров — слишком дорого на каждый запрос; `reltuples` обновляется после `ANALYZE` и подходит для индикативного отображения.

#### Шаг 2.2: Полнотекстовый поиск (1ч)
- `plainto_tsquery('russian', $1)` для пользовательского ввода (безопасен: нет синтаксических ошибок при произвольном тексте)
- Результаты ранжируются через `ts_rank(description_tsv, query)` — заголовок (вес A) важнее описания (вес B)

#### Шаг 2.3: Интеграционные тесты (3ч)
- `pytest-asyncio` + `httpx.AsyncClient` + тестовая БД (отдельный контейнер в `docker-compose.test.yml`)
- Тесты: фильтрация по стеку (AND-логика), cursor пагинация, дедупликация (счётчик не растёт при повторном запуске), cleanup задача, rate limit на `/tasks/fetch`, circuit breaker активируется после N ошибок

---

### Phase 3: Расширения (опционально)

**3.1 Мониторинг (Prometheus + Grafana)** — метрики задач, размер очередей, ошибки. В резюме уже есть: покрываем открытым кодом.

**3.2 Второй источник (Habr Career)** — абстракция `BaseVacancySource`. Демонстрирует extensibility и оправдывает `source` в схеме.

**3.3 skills_mode параметр** — `GET /vacancies?skills=python,fastapi&skills_mode=or` для OR-логики поиска.

**3.4 LLM-обогащение** — маппинг нераспознанных навыков через Claude API; semantic similarity для скора.

**3.5 Telegram-уведомления** — aiogram: новые вакансии с высоким скором, команды `/top`, `/stats`.

---

## 7. Структура проекта

```
job-vacancy-pipeline/
├── docker-compose.yml
├── docker-compose.test.yml
├── .env.example
├── README.md
│
├── app/
│   ├── main.py                    # FastAPI app, lifespan, exception handler
│   ├── config.py                  # pydantic-settings
│   ├── database.py                # AsyncEngine (FastAPI) + SyncEngine (Celery)
│   │
│   ├── models/
│   │   ├── vacancy.py
│   │   └── task_run.py
│   │
│   ├── schemas/
│   │   ├── vacancy.py             # VacancyResponse, VacancyFilter, VacancyList
│   │   ├── task.py
│   │   └── errors.py              # ErrorResponse
│   │
│   ├── api/
│   │   ├── health.py              # GET /health (корень, без /api/v1/)
│   │   └── v1/
│   │       ├── router.py          # сборка роутеров с префиксом /api/v1
│   │       ├── vacancies.py
│   │       └── tasks.py
│   │
│   ├── tasks/
│   │   ├── celery_app.py          # Celery instance, beat schedule, retry config
│   │   ├── fetch.py               # fetch_vacancies
│   │   ├── enrich.py              # enrich_batch
│   │   └── cleanup.py             # cleanup_old_vacancies
│   │
│   └── services/
│       ├── hh_client.py           # httpx.Client, пагинация, error handling
│       ├── dedup.py               # SET NX EX, circuit breaker
│       ├── enrichment.py          # нормализация, скор, грейд
│       ├── skills_map.py          # SKILLS_MAP
│       └── currency.py            # нормализация зарплаты
│
├── migrations/
│   ├── env.py
│   └── versions/
│
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_enrichment.py     # normalize_skill, calc_score (+ NULL-кейс)
    │   └── test_currency.py
    └── integration/
        ├── test_health.py
        ├── test_vacancies_api.py  # фильтры, AND-логика skills, пагинация
        ├── test_fetch_task.py     # дедупликация, upsert, circuit breaker
        └── test_task_ratelimit.py # rate limit на POST /tasks/fetch
```

---

## 8. API Reference

```
GET /health
  Response 200: { "status": "ok",      "postgres": "ok",    "redis": "ok"    }
  Response 503: { "status": "degraded", "postgres": "error", "redis": "ok"    }
  Примечание: без /api/v1/ — load balancer'ы и Docker healthcheck дёргают без версии

GET /api/v1/vacancies
  Query:
    grade           = junior | middle | senior | lead
    work_format     = remote | office | hybrid
    salary_min      = int  (RUB, сравнивается с salary_from_rub)
    salary_max      = int  (RUB, сравнивается с salary_to_rub)
    skills          = python,fastapi  (AND-логика: вакансия должна иметь все)
    search          = str  (plainto_tsquery 'russian', ранжирование по ts_rank)
    min_score       = float 0.0–1.0 (NULL-скоры исключаются)
    limit           = int default 20, max 100
    offset          = int default 0  (Phase 1)
    cursor          = base64         (Phase 2, заменяет offset)
  Response: { "items": [...], "total": int, "next_cursor": str | null }
  Примечание Phase 1: total = COUNT(*) по фильтрам; Phase 2: total_approx из pg_class.reltuples

GET /api/v1/vacancies/{id}
  Response: полная карточка + "skills": ["python", "fastapi", ...]
  Error 404: { "error": { "code": "VACANCY_NOT_FOUND", "message": "..." } }

POST /api/v1/tasks/fetch
  Rate limit: 1 запрос в 5 минут (429 если чаще)
  Body: { "keywords": str?, "area": int? }
  Response 202: { "task_id": "...", "status": "pending" }

GET /api/v1/tasks
  Query: limit (default 20), offset
  Response: { "items": [TaskRun], "total": int }
  Примечание: offset/limit — таблица task_runs небольшая, cursor избыточен
```

---

## 9. Definition of Done

### MVP (Phase 1)
- [ ] `docker-compose up` поднимает систему без ошибок, все healthcheck'и проходят
- [ ] `GET /health` → 200 с живыми PostgreSQL и Redis
- [ ] Celery Beat запускает сбор по расписанию, вакансии появляются в БД
- [ ] Повторный запуск не создаёт дублей (`SELECT COUNT(*)` до и после совпадает)
- [ ] `GET /api/v1/vacancies?skills=python,fastapi` — AND-логика работает корректно
- [ ] `GET /api/v1/vacancies?salary_min=150000` — корректно фильтрует вакансии в USD
- [ ] `relevance_score = NULL` для вакансий без распознанных навыков
- [ ] `updated_at` не меняется при idempotent upsert без изменений данных
- [ ] Circuit breaker срабатывает и отражается в `/health`
- [ ] `POST /api/v1/tasks/fetch` возвращает 429 при частых вызовах
- [ ] Ежедневный cleanup настроен в Beat
- [ ] Unit-тесты проходят (`pytest tests/unit/`)
- [ ] `README.md`: описание, схема архитектуры, инструкция запуска
- [ ] Код на GitHub с осмысленными коммитами
