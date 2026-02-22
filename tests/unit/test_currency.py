def test_rub_passthrough():
    from app.services.currency import to_rub

    assert to_rub(100000, "RUR") == 100000


def test_usd_to_rub():
    from app.config import settings
    from app.services.currency import to_rub

    assert to_rub(1000, "USD") == round(1000 * settings.USD_TO_RUB)


def test_none_amount():
    from app.services.currency import to_rub

    assert to_rub(None, "USD") is None


def test_unknown_currency():
    from app.services.currency import to_rub

    assert to_rub(1000, "GBP") is None
