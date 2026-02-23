from app.models.task_run import TaskRun
from app.repositories.task import TaskRepository


class TriggerFetchUseCase:
    def __init__(self, repo: TaskRepository):
        self._repo = repo

    async def execute(self) -> TaskRun:
        from app.tasks.fetch import fetch_vacancies

        task_run = TaskRun(task_name="fetch_vacancies", status="pending")
        saved = await self._repo.save(task_run)
        fetch_vacancies.delay(task_run_id=str(saved.id))
        return saved
