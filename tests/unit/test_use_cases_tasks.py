import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.task import TaskRepository
from app.use_cases.tasks.get_task_status import GetTaskStatusUseCase
from app.use_cases.tasks.trigger_fetch import TriggerFetchUseCase


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


@pytest.mark.asyncio
async def test_trigger_fetch_returns_saved_task():
    mock_repo = AsyncMock(spec=TaskRepository)
    saved = _make_task(status="pending")
    mock_repo.save.return_value = saved

    with patch("app.tasks.fetch.fetch_vacancies") as mock_task:
        mock_task.delay = MagicMock()
        result = await TriggerFetchUseCase(mock_repo).execute()

    assert result is saved
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_trigger_fetch_calls_celery_delay():
    mock_repo = AsyncMock(spec=TaskRepository)
    saved = _make_task(status="pending")
    mock_repo.save.return_value = saved

    with patch("app.tasks.fetch.fetch_vacancies") as mock_task:
        mock_task.delay = MagicMock()
        await TriggerFetchUseCase(mock_repo).execute()

    mock_task.delay.assert_called_once_with(task_run_id=str(saved.id))


@pytest.mark.asyncio
async def test_trigger_fetch_saves_with_correct_name():
    mock_repo = AsyncMock(spec=TaskRepository)
    mock_repo.save.return_value = _make_task()

    with patch("app.tasks.fetch.fetch_vacancies") as mock_task:
        mock_task.delay = MagicMock()
        await TriggerFetchUseCase(mock_repo).execute()

    saved_task_run = mock_repo.save.call_args.args[0]
    assert saved_task_run.task_name == "fetch_vacancies"
    assert saved_task_run.status == "pending"


@pytest.mark.asyncio
async def test_get_task_status_returns_task():
    mock_repo = AsyncMock(spec=TaskRepository)
    task = _make_task(status="running")
    mock_repo.get.return_value = task

    result = await GetTaskStatusUseCase(mock_repo).execute(task.id)

    assert result is task


@pytest.mark.asyncio
async def test_get_task_status_returns_none_when_not_found():
    mock_repo = AsyncMock(spec=TaskRepository)
    mock_repo.get.return_value = None

    result = await GetTaskStatusUseCase(mock_repo).execute(uuid.uuid4())

    assert result is None
