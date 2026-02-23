from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.vacancy import Vacancy


class VacancyRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list(
        self,
        grade: str | None = None,
        work_format: str | None = None,
        min_relevance: float | None = None,
        min_salary_rub: int | None = None,
        max_salary_rub: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Vacancy], int]:
        filters = []
        if grade is not None:
            filters.append(Vacancy.grade == grade)
        if work_format is not None:
            filters.append(Vacancy.work_format == work_format)
        if min_relevance is not None:
            filters.append(Vacancy.relevance_score >= min_relevance)
        if min_salary_rub is not None:
            filters.append(Vacancy.salary_from_rub >= min_salary_rub)
        if max_salary_rub is not None:
            filters.append(Vacancy.salary_to_rub <= max_salary_rub)

        count_q = select(func.count()).select_from(Vacancy)
        if filters:
            count_q = count_q.where(*filters)
        total_result = await self._session.execute(count_q)
        total = total_result.scalar_one()

        items_q = (
            select(Vacancy)
            .options(selectinload(Vacancy.skills))
            .order_by(
                Vacancy.relevance_score.desc().nulls_last(),
                Vacancy.published_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        if filters:
            items_q = items_q.where(*filters)
        items_result = await self._session.execute(items_q)
        vacancies = list(items_result.scalars().all())

        return vacancies, total
