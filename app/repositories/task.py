import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_run import TaskRun


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, task_id: uuid.UUID) -> TaskRun | None:
        return await self._session.get(TaskRun, task_id)

    async def save(self, task_run: TaskRun) -> TaskRun:
        self._session.add(task_run)
        await self._session.flush()
        await self._session.refresh(task_run)
        await self._session.commit()
        return task_run
