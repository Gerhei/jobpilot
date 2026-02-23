import uuid

from app.models.task_run import TaskRun
from app.repositories.task import TaskRepository


class GetTaskStatusUseCase:
    def __init__(self, repo: TaskRepository):
        self._repo = repo

    async def execute(self, task_id: uuid.UUID) -> TaskRun | None:
        return await self._repo.get(task_id)
