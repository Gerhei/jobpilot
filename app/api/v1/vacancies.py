from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.repositories.vacancy import VacancyRepository
from app.schemas.vacancy import VacancyListResponse
from app.use_cases.vacancies.list_vacancies import (
    ListVacanciesInput,
    ListVacanciesUseCase,
)

router = APIRouter()


@router.get("/vacancies", response_model=VacancyListResponse)
async def get_vacancies(
    grade: str | None = Query(None),
    work_format: str | None = Query(None),
    min_relevance: float | None = Query(None, ge=0.0, le=1.0),
    min_salary_rub: int | None = Query(None, ge=0),
    max_salary_rub: int | None = Query(None, ge=0),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
):
    use_case = ListVacanciesUseCase(VacancyRepository(session))
    vacancies, total = await use_case.execute(
        ListVacanciesInput(
            grade=grade,
            work_format=work_format,
            min_relevance=min_relevance,
            min_salary_rub=min_salary_rub,
            max_salary_rub=max_salary_rub,
            limit=limit,
            offset=offset,
        )
    )
    return VacancyListResponse(items=vacancies, total=total, limit=limit, offset=offset)
