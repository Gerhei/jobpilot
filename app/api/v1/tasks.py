import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.repositories.task import TaskRepository
from app.schemas.task import TaskRunOut, TaskTriggerResponse
from app.use_cases.tasks.get_task_status import GetTaskStatusUseCase
from app.use_cases.tasks.trigger_fetch import TriggerFetchUseCase

router = APIRouter()


@router.post("/tasks/fetch", response_model=TaskTriggerResponse, status_code=202)
async def trigger_fetch(session: AsyncSession = Depends(get_async_session)):
    task_run = await TriggerFetchUseCase(TaskRepository(session)).execute()
    return TaskTriggerResponse(task_run_id=task_run.id, status=task_run.status)


@router.get("/tasks/{task_id}", response_model=TaskRunOut)
async def get_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    task_run = await GetTaskStatusUseCase(TaskRepository(session)).execute(task_id)
    if task_run is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_run
