from app.models.task_run import TaskRun
from app.models.vacancy import Vacancy, VacancySkill


def test_vacancy_tablename():
    assert Vacancy.__tablename__ == "vacancies"


def test_vacancy_skill_tablename():
    assert VacancySkill.__tablename__ == "vacancy_skills"


def test_task_run_tablename():
    assert TaskRun.__tablename__ == "task_runs"


def test_vacancy_unique_constraint_exists():
    constraints = {c.name for c in Vacancy.__table__.constraints}
    assert "uq_vacancy_source" in constraints


def test_vacancy_required_columns():
    cols = {c.name for c in Vacancy.__table__.columns}
    for required in (
        "id",
        "external_id",
        "source",
        "title",
        "url",
        "published_at",
        "fetched_at",
        "updated_at",
    ):
        assert required in cols, f"Missing column: {required}"


def test_task_run_status_column_exists():
    cols = {c.name for c in TaskRun.__table__.columns}
    assert "status" in cols
    assert "meta" in cols
    assert "vacancies_fetched" in cols
    assert "vacancies_saved" in cols


def test_vacancy_skill_fk_cascade():
    fk = list(VacancySkill.__table__.foreign_keys)[0]
    assert fk.column.table.name == "vacancies"
    assert "CASCADE" in fk.ondelete.upper()
