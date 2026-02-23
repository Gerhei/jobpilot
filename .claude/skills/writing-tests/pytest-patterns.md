# pytest Patterns

## Параметризация

Когда нужно покрыть много edge cases без дублирования тела теста:

```python
# Плохо — три одинаковых теста
def test_empty_string():
    assert normalize("") == ""

def test_with_dashes():
    assert normalize("AB-123") == "AB123"

def test_lowercase():
    assert normalize("ab123") == "AB123"

# Хорошо — одно правило, много наборов данных
@pytest.mark.parametrize("input,expected", [
    ("", ""),
    ("AB-123", "AB123"),
    ("ab123", "AB123"),
    ("  ab 123  ", "AB123"),   # whitespace
    (None, None),              # None input
], ids=["empty", "dashes", "lowercase", "whitespace", "none"])
def test_part_number_normalization(input, expected):
    assert normalize(input) == expected
```

Имя теста описывает правило в целом, конкретику несут `ids`.

---

## Фабрики тестовых данных

Когда объект имеет много полей, а тест проверяет одно:

```python
# Плохо — вручную заполняем всё, непонятно что важно для теста
def test_discount_for_vip():
    order = Order(
        id=1, user_id=42, items=[...], status="pending",
        created_at=datetime.now(), is_vip=True,  # ← это важно
        shipping_address="...", payment_method="card"
    )
    assert calculate_discount(order) == 0.15

# Хорошо — фабрика с дефолтами, в тесте только важное
def make_order(**kwargs) -> Order:
    defaults = dict(
        id=1, user_id=42, items=[], status="pending",
        created_at=datetime(2024, 1, 1), is_vip=False,
        shipping_address="test addr", payment_method="card"
    )
    return Order(**{**defaults, **kwargs})

def test_discount_for_vip():
    order = make_order(is_vip=True)
    assert calculate_discount(order) == 0.15

def test_no_discount_for_regular():
    order = make_order(is_vip=False)
    assert calculate_discount(order) == 0.0
```

Альтернативы: `factory_boy`, `dataclasses` с дефолтами, `pydantic` модели.

---

## Фикстуры и scope

```python
# function scope (дефолт) — свежий объект для каждого теста
@pytest.fixture
def db_session():
    session = create_test_session()
    yield session
    session.rollback()

# session scope — только для immutable/stateless ресурсов
@pytest.fixture(scope="session")
def http_client():
    return httpx.Client(base_url="http://testserver")

# Никогда — session scope для мутабельного состояния
# @pytest.fixture(scope="session")
# def db_session():  # ← грязные данные между тестами!
```

---

## Async тесты (pytest-asyncio)

```python
# Пометить тест
@pytest.mark.asyncio
async def test_async_parser():
    result = await parse_catalog_page(html)
    assert result.part_number == "AB123"

# Async фикстура
@pytest.fixture
async def async_client():
    async with httpx.AsyncClient() as client:
        yield client

# Мокать корутину — AsyncMock, не MagicMock
from unittest.mock import AsyncMock, patch

async def test_llm_call():
    with patch("mymodule.call_claude", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"part_number": "AB123"}
        result = await extract_parts(html)
        assert result[0].part_number == "AB123"

# FastAPI endpoint тесты
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_parse_endpoint(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/parse", json={"url": "http://example.com"})
    assert response.status_code == 200
```

Event loop scope: по умолчанию каждый тест получает свой loop (`function` scope) — не меняй на `session` без веской причины.

---

## Проверка исключений

```python
# Базовая
def test_raises_on_invalid_input():
    with pytest.raises(ValueError):
        normalize_part_number(123)  # ожидаем int, не str

# С проверкой сообщения — только когда сообщение часть контракта
def test_raises_with_message():
    with pytest.raises(ValueError, match="Part number cannot be empty"):
        normalize_part_number("")

# Исключение как возврат default — тоже контракт
def test_returns_none_on_missing():
    result = find_part("NONEXISTENT")
    assert result is None
```

---

## Приблизительные сравнения и подмножества

```python
# Числа с плавающей точкой
assert price == pytest.approx(19.99, rel=1e-3)

# Проверять только релевантные поля, не весь объект
def test_normalization_cleans_part_number():
    result = normalize_catalog_entry(raw_entry)
    # Проверяем только то, что относится к нормализации
    assert result.part_number == "AB123"
    assert result.part_number_normalized is True
    # НЕ проверяем result.price, result.description и т.д. — не часть контракта

# Для сложных вложенных структур — точечные проверки
def test_agent_extracts_table_data():
    result = run_agent(html_with_table)
    assert len(result.rows) == 5
    assert result.rows[0]["part_number"] == "AB-001"
    assert result.headers == ["Part Number", "Description", "Price"]
```

---

## Мокирование времени и случайности

```python
from unittest.mock import patch
from freezegun import freeze_time

# Время
@freeze_time("2024-01-15 10:00:00")
def test_cache_expiry():
    cache.set("key", "value", ttl=3600)
    assert cache.is_valid("key") is True

# Или через patch
def test_with_fixed_time():
    with patch("mymodule.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2024, 1, 15)
        result = create_timestamped_entry("data")
    assert result.created_at == datetime(2024, 1, 15)

# Случайность
def test_with_fixed_random():
    with patch("random.random", return_value=0.5):
        result = sample_with_probability(0.7)
    assert result is True
```

---

## Интеграционные тесты с БД

```python
# Откат после теста — изоляция без удаления данных
@pytest.fixture
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

# Или через pytest-postgresql / testcontainers для полной изоляции
@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:15") as pg:
        yield pg.get_connection_url()
```
