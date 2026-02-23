from app.config import settings


def to_rub(amount: int | None, currency: str | None) -> int | None:
    """Конвертирует сумму в рубли. None если неизвестная валюта или нет суммы."""
    if amount is None or currency is None:
        return None
    rates: dict[str, float] = {
        "RUR": 1.0,
        "RUB": 1.0,
        "USD": settings.USD_TO_RUB,
        "EUR": settings.EUR_TO_RUB,
        "KZT": settings.KZT_TO_RUB,
    }
    rate = rates.get(currency.upper())
    if rate is None:
        return None
    return round(amount * rate)
