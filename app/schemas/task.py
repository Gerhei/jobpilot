import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskRunOut(BaseModel):
    id: uuid.UUID
    task_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    error: str | None
    vacancies_fetched: int | None
    vacancies_saved: int | None

    model_config = ConfigDict(from_attributes=True)


class TaskTriggerResponse(BaseModel):
    task_run_id: uuid.UUID
    status: str  # "pending"
