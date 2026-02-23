import logging
import uuid
from datetime import datetime, timezone

import redis as redis_lib

from app.config import settings
from app.database import SyncSessionLocal
from app.models.task_run import TaskRun
from app.services.dedup import DedupService
from app.services.hh_client import HHAPIError, HHClient
from app.tasks.celery_app import celery_app
from app.tasks.enrich import enrich_batch

logger = logging.getLogger(__name__)
UTC = timezone.utc


@celery_app.task(bind=True, max_retries=3, name="app.tasks.fetch.fetch_vacancies")
def fetch_vacancies(self, task_run_id: str | None = None) -> dict:
    r = redis_lib.from_url(settings.REDIS_URL)
    dedup = DedupService(r)

    if dedup.is_circuit_open():
        logger.warning("Circuit open, skipping fetch")
        if task_run_id is not None:
            _finish_task(
                uuid.UUID(task_run_id),
                "failure",
                error="circuit_open",
            )
        return {"status": "skipped", "reason": "circuit_open"}

    with SyncSessionLocal() as session:
        if task_run_id is not None:
            task_run = session.get(TaskRun, uuid.UUID(task_run_id))
            task_run.status = "running"
            session.commit()
        else:
            task_run = TaskRun(task_name="fetch_vacancies", status="running")
            session.add(task_run)
            session.commit()
        task_run_id = task_run.id

    vacancies_fetched = 0
    batch: list[dict] = []

    try:
        with HHClient(base_url=settings.HH_API_BASE_URL) as client:
            page = 0
            while True:
                data = client.search_vacancies(
                    text=settings.HH_SEARCH_KEYWORDS,
                    area=settings.HH_AREA_ID,
                    page=page,
                    per_page=100,
                )
                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    ext_id = str(item["id"])
                    if not dedup.is_new("hh", ext_id):
                        continue
                    try:
                        detail = client.get_vacancy(ext_id)
                    except HHAPIError as e:
                        if "403" in str(e):
                            logger.warning("Skipping vacancy %s: %s", ext_id, e)
                            continue
                        raise
                    batch.append(detail)
                    vacancies_fetched += 1
                    if len(batch) >= 20:
                        enrich_batch.delay(batch)
                        batch = []

                total_pages = data.get("pages", 1)
                page += 1
                if page >= total_pages:
                    break

        if batch:
            enrich_batch.delay(batch)

        dedup.record_success()
        _finish_task(task_run_id, "success", vacancies_fetched=vacancies_fetched)
        return {"status": "success", "vacancies_fetched": vacancies_fetched}

    except HHAPIError as exc:
        dedup.record_failure(
            settings.CIRCUIT_BREAKER_THRESHOLD,
            settings.CIRCUIT_BREAKER_TIMEOUT,
        )
        _finish_task(task_run_id, "failure", error=str(exc))
        raise self.retry(exc=exc, countdown=2**self.request.retries)

    except Exception as exc:
        _finish_task(task_run_id, "failure", error=str(exc))
        raise


def _finish_task(
    task_run_id,
    status: str,
    error: str | None = None,
    vacancies_fetched: int | None = None,
) -> None:
    with SyncSessionLocal() as session:
        tr = session.get(TaskRun, task_run_id)
        if tr is None:
            logger.error("TaskRun %s not found in _finish_task", task_run_id)
            return
        tr.status = status
        tr.finished_at = datetime.now(tz=UTC)
        tr.error = error
        tr.vacancies_fetched = vacancies_fetched
        session.commit()
