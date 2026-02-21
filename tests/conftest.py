import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def app_with_mocked_deps():
    """FastAPI-приложение с замоканными postgres и redis проверками."""
    from app.main import create_app

    app = create_app()

    with patch("app.api.health.check_postgres", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_redis", return_value=True):
        yield app


@pytest.fixture
def app_with_postgres_down():
    """FastAPI-приложение с недоступным postgres."""
    from app.main import create_app

    app = create_app()

    with patch("app.api.health.check_postgres", new_callable=AsyncMock, return_value=False), \
         patch("app.api.health.check_redis", return_value=True):
        yield app
