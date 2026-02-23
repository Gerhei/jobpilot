import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_async_session
from app.main import create_app


def _make_task(status: str = "pending") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        task_name="fetch_vacancies",
        status=status,
        started_at=datetime.now(tz=timezone.utc),
        finished_at=None,
        error=None,
        vacancies_fetched=None,
        vacancies_saved=None,
    )


@pytest.fixture
def test_app():
    app = create_app()

    async def mock_session():
        yield MagicMock()

    app.dependency_overrides[get_async_session] = mock_session
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_fetch_returns_202(test_app):
    task_run = _make_task(status="pending")

    with patch("app.api.v1.tasks.TriggerFetchUseCase") as MockUC:
        instance = AsyncMock()
        instance.execute.return_value = task_run
        MockUC.return_value = instance

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/tasks/fetch")

    assert response.status_code == 202
    data = response.json()
    assert data["task_run_id"] == str(task_run.id)
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_task_returns_200(test_app):
    task_run = _make_task(status="running")

    with patch("app.api.v1.tasks.GetTaskStatusUseCase") as MockUC:
        instance = AsyncMock()
        instance.execute.return_value = task_run
        MockUC.return_value = instance

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/tasks/{task_run.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(task_run.id)
    assert data["status"] == "running"
    assert data["task_name"] == "fetch_vacancies"


@pytest.mark.asyncio
async def test_get_task_returns_404_when_not_found(test_app):
    task_id = uuid.uuid4()

    with patch("app.api.v1.tasks.GetTaskStatusUseCase") as MockUC:
        instance = AsyncMock()
        instance.execute.return_value = None
        MockUC.return_value = instance

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/tasks/{task_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


@pytest.mark.asyncio
async def test_get_task_invalid_uuid_returns_422(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/tasks/not-a-uuid")

    assert response.status_code == 422
