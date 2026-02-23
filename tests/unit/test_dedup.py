from unittest.mock import MagicMock

from app.services.dedup import DedupService


def test_is_new_true_for_new_key():
    r = MagicMock()
    r.set.return_value = True
    assert DedupService(r).is_new("hh", "123") is True


def test_is_new_false_for_existing_key():
    r = MagicMock()
    r.set.return_value = None
    assert DedupService(r).is_new("hh", "123") is False


def test_circuit_opens_after_threshold():
    r = MagicMock()
    r.incr.return_value = 5
    svc = DedupService(r)
    svc.record_failure(threshold=5, timeout=3600)
    r.set.assert_called_once_with("circuit_open", 1, ex=3600)


def test_circuit_not_opens_below_threshold():
    r = MagicMock()
    r.incr.return_value = 3
    DedupService(r).record_failure(threshold=5, timeout=3600)
    r.set.assert_not_called()


def test_is_circuit_open():
    r = MagicMock()
    r.exists.return_value = 1
    assert DedupService(r).is_circuit_open() is True
