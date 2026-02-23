from redis import Redis

_DEDUP_TTL = 35 * 86400  # 35 дней
_CIRCUIT_KEY = "circuit_open"
_FAILURES_KEY = "circuit_failures"


class DedupService:
    def __init__(self, redis: Redis):
        self._r = redis

    def is_new(self, source: str, external_id: str) -> bool:
        """True если вакансия новая (SET NX), False — уже видели."""
        key = f"seen:{source}:{external_id}"
        return self._r.set(key, 1, nx=True, ex=_DEDUP_TTL) is not None

    def is_circuit_open(self) -> bool:
        return bool(self._r.exists(_CIRCUIT_KEY))

    def record_success(self) -> None:
        self._r.delete(_FAILURES_KEY)

    def record_failure(self, threshold: int, timeout: int) -> None:
        failures = self._r.incr(_FAILURES_KEY)
        if failures >= threshold:
            self._r.set(_CIRCUIT_KEY, 1, ex=timeout)
            self._r.delete(_FAILURES_KEY)
