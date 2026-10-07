from decimal import Decimal

import httpx2
from django.core.cache import cache

from parcels.models import Parcel

CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
CACHE_KEY = "usd_rub_rate"
CACHE_TTL = 3600  # 1 час


def get_usd_rub_rate() -> Decimal:
    """Возвращает курс USD/RUB с кешем в Redis на 1 час."""

    cached = cache.get(CACHE_KEY)
    if cached:
        return Decimal(cached)

    response = httpx2.get(CBR_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    rate = Decimal(str(data["Valute"]["USD"]["Value"]))

    cache.set(CACHE_KEY, str(rate), CACHE_TTL)
    return rate


def compute_delivery_cost(parcel: Parcel, rate: Decimal) -> Decimal:
    """Чистая формула: (weight * 0.5 + content_cost_usd * 0.01) * rate."""

    return (parcel.weight * Decimal("0.5") + parcel.content_cost_usd * Decimal("0.01")) * rate


def calculate_delivery_cost(parcel: Parcel) -> Decimal:
    """Обёртка: сама достаёт курс. Для одиночных вызовов и тестов."""

    return compute_delivery_cost(parcel, get_usd_rub_rate())
