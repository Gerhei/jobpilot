from dataclasses import dataclass

from app.models.vacancy import Vacancy
from app.repositories.vacancy import VacancyRepository


@dataclass
class ListVacanciesInput:
    grade: str | None = None
    work_format: str | None = None
    min_relevance: float | None = None
    min_salary_rub: int | None = None
    max_salary_rub: int | None = None
    limit: int = 20
    offset: int = 0


class ListVacanciesUseCase:
    def __init__(self, repo: VacancyRepository):
        self._repo = repo

    async def execute(self, inp: ListVacanciesInput) -> tuple[list[Vacancy], int]:
        return await self._repo.list(
            grade=inp.grade,
            work_format=inp.work_format,
            min_relevance=inp.min_relevance,
            min_salary_rub=inp.min_salary_rub,
            max_salary_rub=inp.max_salary_rub,
            limit=inp.limit,
            offset=inp.offset,
        )
