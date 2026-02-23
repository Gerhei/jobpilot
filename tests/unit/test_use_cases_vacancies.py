from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.vacancy import VacancyRepository
from app.use_cases.vacancies.list_vacancies import (
    ListVacanciesInput,
    ListVacanciesUseCase,
)


@pytest.mark.asyncio
async def test_list_vacancies_empty():
    mock_repo = AsyncMock(spec=VacancyRepository)
    mock_repo.list.return_value = ([], 0)

    use_case = ListVacanciesUseCase(mock_repo)
    vacancies, total = await use_case.execute(ListVacanciesInput())

    assert vacancies == []
    assert total == 0


@pytest.mark.asyncio
async def test_list_vacancies_with_results():
    mock_repo = AsyncMock(spec=VacancyRepository)
    v1, v2 = MagicMock(), MagicMock()
    mock_repo.list.return_value = ([v1, v2], 2)

    use_case = ListVacanciesUseCase(mock_repo)
    vacancies, total = await use_case.execute(ListVacanciesInput())

    assert len(vacancies) == 2
    assert total == 2


@pytest.mark.asyncio
async def test_list_vacancies_passes_filters():
    mock_repo = AsyncMock(spec=VacancyRepository)
    mock_repo.list.return_value = ([], 0)

    inp = ListVacanciesInput(
        grade="senior",
        work_format="remote",
        min_relevance=0.5,
        min_salary_rub=100_000,
        max_salary_rub=300_000,
        limit=10,
        offset=5,
    )
    await ListVacanciesUseCase(mock_repo).execute(inp)

    mock_repo.list.assert_called_once_with(
        grade="senior",
        work_format="remote",
        min_relevance=0.5,
        min_salary_rub=100_000,
        max_salary_rub=300_000,
        limit=10,
        offset=5,
    )


@pytest.mark.asyncio
async def test_list_vacancies_default_pagination():
    mock_repo = AsyncMock(spec=VacancyRepository)
    mock_repo.list.return_value = ([], 0)

    await ListVacanciesUseCase(mock_repo).execute(ListVacanciesInput())

    kwargs = mock_repo.list.call_args.kwargs
    assert kwargs["limit"] == 20
    assert kwargs["offset"] == 0
