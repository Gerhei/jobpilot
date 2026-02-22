import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200_when_services_up(app_with_mocked_deps):
    """Health endpoint возвращает 200 когда postgres и redis доступны."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_mocked_deps), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["postgres"] == "ok"
    assert body["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_returns_503_when_postgres_down(app_with_postgres_down):
    """Health endpoint возвращает 503 когда postgres недоступен."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_postgres_down), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["postgres"] == "error"
    assert body["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_response_has_all_keys(app_with_mocked_deps):
    """Health endpoint всегда возвращает все три ключа."""
    async with AsyncClient(
        transport=ASGITransport(app=app_with_mocked_deps), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    body = response.json()
    assert "status" in body
    assert "postgres" in body
    assert "redis" in body
