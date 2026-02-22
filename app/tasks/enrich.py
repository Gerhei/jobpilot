import logging
from datetime import datetime, timezone

from sqlalchemy import case, func, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import SyncSessionLocal
from app.models.vacancy import Vacancy, VacancySkill
from app.services.currency import to_rub
from app.services.enrichment import (
    calc_relevance_score,
    extract_grade,
    extract_skills,
    extract_work_format,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
UTC = timezone.utc


@celery_app.task(name="app.tasks.enrich.enrich_batch")
def enrich_batch(vacancies_data: list[dict]) -> dict:
    saved = 0
    with SyncSessionLocal() as session:
        for v in vacancies_data:
            skills = extract_skills(v.get("key_skills", []), v.get("description"))
            score = calc_relevance_score(skills, settings.reference_skills_set)
            salary = v.get("salary") or {}
            currency = salary.get("currency")
            sal_from = salary.get("from")
            sal_to = salary.get("to")
            pub_at_str = v.get("published_at")
            pub_at = (
                datetime.fromisoformat(pub_at_str)
                if pub_at_str
                else datetime.now(tz=UTC)
            )
            full_text = (v.get("name") or "") + " " + (v.get("description") or "")

            row = {
                "external_id": str(v["id"]),
                "source": "hh",
                "title": v.get("name", ""),
                "company": (v.get("employer") or {}).get("name"),
                "description": v.get("description"),
                "salary_from": sal_from,
                "salary_to": sal_to,
                "currency": currency,
                "salary_from_rub": to_rub(sal_from, currency),
                "salary_to_rub": to_rub(sal_to, currency),
                "grade": extract_grade(full_text),
                "work_format": extract_work_format(full_text),
                "url": v.get("alternate_url", ""),
                "relevance_score": score,
                "published_at": pub_at,
            }

            stmt = pg_insert(Vacancy).values(**row)
            updated_at_expr = case(
                (
                    or_(
                        Vacancy.description.is_distinct_from(stmt.excluded.description),
                        Vacancy.salary_from.is_distinct_from(stmt.excluded.salary_from),
                        Vacancy.salary_to.is_distinct_from(stmt.excluded.salary_to),
                    ),
                    func.now(),
                ),
                else_=Vacancy.updated_at,
            )
            update_set = {c: stmt.excluded[c] for c in row if c != "external_id"}
            update_set["updated_at"] = updated_at_expr

            result = session.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_vacancy_source", set_=update_set
                ).returning(Vacancy.id)
            )
            vacancy_id = result.scalar_one()

            if skills:
                session.execute(
                    pg_insert(VacancySkill)
                    .values([{"vacancy_id": vacancy_id, "skill": s} for s in skills])
                    .on_conflict_do_nothing()
                )

            saved += 1

        session.commit()

    return {"vacancies_saved": saved}
