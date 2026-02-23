from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_async_session
from app.main import create_app


@pytest.fixture
def test_app():
    app = create_app()

    async def mock_session():
        yield MagicMock()

    app.dependency_overrides[get_async_session] = mock_session
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_vacancies_returns_200_with_empty_list(test_app):
    with patch("app.api.v1.vacancies.ListVacanciesUseCase") as MockUC:
        instance = AsyncMock()
        instance.execute.return_value = ([], 0)
        MockUC.return_value = instance

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/vacancies")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_get_vacancies_query_params_forwarded(test_app):
    with patch("app.api.v1.vacancies.ListVacanciesUseCase") as MockUC:
        instance = AsyncMock()
        instance.execute.return_value = ([], 0)
        MockUC.return_value = instance

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            await client.get(
                "/api/v1/vacancies",
                params={
                    "grade": "senior",
                    "work_format": "remote",
                    "min_relevance": 0.5,
                    "limit": 10,
                    "offset": 5,
                },
            )

    call_input = instance.execute.call_args.args[0]
    assert call_input.grade == "senior"
    assert call_input.work_format == "remote"
    assert call_input.min_relevance == 0.5
    assert call_input.limit == 10
    assert call_input.offset == 5


@pytest.mark.asyncio
async def test_get_vacancies_invalid_limit_returns_422(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/vacancies", params={"limit": 200})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_vacancies_invalid_min_relevance_returns_422(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/vacancies", params={"min_relevance": 1.5})

    assert response.status_code == 422
