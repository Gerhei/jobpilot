import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RATE_LIMIT_FALLBACK = 60


class HHAPIError(Exception):
    pass


class HHClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"User-Agent": "JobPilot/1.0 (vacancy aggregator)"},
        )

    def _get(self, path: str, params: dict | None = None) -> Any:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._client.get(path, params=params)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", _RATE_LIMIT_FALLBACK))
                    logger.warning("hh.ru 429, sleep %ds", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code == 403:
                    raise HHAPIError(f"403 Forbidden: {path}")
                resp.raise_for_status()
                return resp.json()
            except HHAPIError:
                raise
            except Exception as exc:
                last_exc = exc
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "hh.ru error attempt %d/%d: %s, sleep %ds",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)
        raise HHAPIError(
            f"hh.ru unreachable after {_MAX_RETRIES} retries"
        ) from last_exc

    def search_vacancies(
        self, text: str, area: int = 1, page: int = 0, per_page: int = 100
    ) -> dict:
        return self._get(
            "/vacancies",
            params={"text": text, "area": area, "page": page, "per_page": per_page},
        )

    def get_vacancy(self, vacancy_id: str) -> dict:
        return self._get(f"/vacancies/{vacancy_id}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HHClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
