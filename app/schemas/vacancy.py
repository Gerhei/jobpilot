import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class VacancyOut(BaseModel):
    id: uuid.UUID
    external_id: str
    source: str
    title: str
    company: str | None
    url: str
    grade: str | None
    work_format: str | None
    salary_from: int | None
    salary_to: int | None
    currency: str | None
    salary_from_rub: int | None
    salary_to_rub: int | None
    relevance_score: float | None
    published_at: datetime
    fetched_at: datetime
    updated_at: datetime
    skills: list[str]

    model_config = ConfigDict(from_attributes=True)

    @field_validator("skills", mode="before")
    @classmethod
    def extract_skill_names(cls, v):
        if v and hasattr(v[0], "skill"):
            return [s.skill for s in v]
        return v


class VacancyListResponse(BaseModel):
    items: list[VacancyOut]
    total: int
    limit: int
    offset: int
