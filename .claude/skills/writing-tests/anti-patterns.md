# Антипаттерны тестирования

---

## Тест проверяет реализацию, а не поведение

```python
# Плохо — знает о внутренней переменной _cache
def test_caching():
    parser = CatalogParser()
    parser.parse(url)
    assert url in parser._cache  # упадёт при любом рефакторинге кеша

# Хорошо — проверяет наблюдаемое поведение
def test_second_parse_uses_cache():
    parser = CatalogParser()
    with patch("mymodule.fetch_url") as mock_fetch:
        parser.parse(url)
        parser.parse(url)
    mock_fetch.assert_called_once()  # fetch был только один раз — кеш работает
```

---

## Mock вместо проверки результата

```python
# Плохо — проверяем вызов, хотя нас интересует результат
def test_normalizer_calls_strip():
    with patch("str.strip") as mock_strip:
        normalize("  AB123  ")
    mock_strip.assert_called()  # это тест реализации

# Хорошо — проверяем результат
def test_normalizer_trims_whitespace():
    assert normalize("  AB123  ") == "AB123"
```

Мок на вызов оправдан только когда сам вызов — контракт: "сообщение отправлено в очередь", "метрика записана".

---

## Слишком много моков → проблема архитектуры

```python
# Плохо — 5 моков, функция делает слишком много
def test_process_order():
    with patch("db.save") as mock_db, \
         patch("email.send") as mock_email, \
         patch("inventory.reserve") as mock_inv, \
         patch("payment.charge") as mock_pay, \
         patch("logger.info") as mock_log:
        process_order(order)
    # что именно мы тестируем?..

# Сигнал: пора разбить функцию или инвертировать зависимости
```

---

## Тест зависит от другого теста

```python
# Плохо — test_2 зависит от побочного эффекта test_1
def test_1_creates_user():
    db.create_user("alice")
    assert db.user_exists("alice")

def test_2_user_has_default_role():
    # упадёт если test_1 не запустился или запустился после
    user = db.get_user("alice")
    assert user.role == "viewer"

# Хорошо — каждый тест создаёт своё состояние
@pytest.fixture
def alice(db_session):
    return db_session.create_user("alice")

def test_user_has_default_role(alice):
    assert alice.role == "viewer"
```

---

## Session-scope фикстура с мутабельным состоянием

```python
# Плохо — один тест меняет список, следующий получает грязные данные
@pytest.fixture(scope="session")
def part_list():
    return ["AB123", "CD456"]

def test_adds_part(part_list):
    part_list.append("EF789")  # мутирует!
    assert "EF789" in part_list

def test_original_parts(part_list):
    assert part_list == ["AB123", "CD456"]  # упадёт — список уже изменён

# Хорошо — function scope, каждый тест получает свежую копию
@pytest.fixture
def part_list():
    return ["AB123", "CD456"]
```

---

## Тест проверяет весь объект вместо контракта

```python
# Плохо — хрупко: любое новое поле или изменение несвязанного поля роняет тест
def test_part_normalization():
    result = normalize_entry(raw)
    assert result == ParsedEntry(
        part_number="AB123",
        description="Brake pad",
        price=19.99,
        currency="USD",
        in_stock=True,
        # ... ещё 10 полей
    )

# Хорошо — проверяем только то, что относится к нормализации
def test_part_number_normalized():
    result = normalize_entry(raw)
    assert result.part_number == "AB123"
    assert result.part_number == result.part_number.upper()
```

---

## Тест без явных входных данных

```python
# Плохо — непонятно, что влияет на результат теста
def test_discount_applied(order_fixture, user_fixture, pricing_fixture):
    result = calculate_discount(order_fixture, user_fixture)
    assert result == 0.15  # почему 15%? откуда это число?

# Хорошо — критичные данные явно в теле теста
def test_vip_gets_15_percent_discount():
    order = make_order(subtotal=100.0)
    user = make_user(is_vip=True, loyalty_years=3)
    assert calculate_discount(order, user) == 0.15
```

---

## Мок корутины через MagicMock вместо AsyncMock

```python
# Плохо — MagicMock не поддерживает await
async def test_bad():
    with patch("mymodule.fetch", MagicMock(return_value={"data": 1})):
        result = await process()  # TypeError: object MagicMock can't be used in await

# Хорошо
async def test_good():
    with patch("mymodule.fetch", AsyncMock(return_value={"data": 1})):
        result = await process()
    assert result == {"data": 1}
```
