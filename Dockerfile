FROM python:3.12-slim

# Установить uv из официального образа
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Копировать файлы зависимостей отдельным слоем — кэш не инвалидируется при смене кода
COPY pyproject.toml uv.lock ./

# Установить зависимости (без dev)
RUN uv sync --frozen --no-dev

# Копировать исходный код
COPY . .

# По умолчанию — запуск API; переопределяется в docker-compose для worker/beat
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
