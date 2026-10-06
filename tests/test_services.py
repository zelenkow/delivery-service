from decimal import Decimal

import pytest
from pytest_mock import MockerFixture

from parcels.models import Parcel, ParcelType
from parcels.services import calculate_delivery_cost, get_usd_rub_rate


@pytest.mark.django_db
def test_get_usd_rub_rate_returns_decimal(mocker: MockerFixture) -> None:
    """Курс возвращается как Decimal."""

    # Мокаем кэш и HTTP по путям, которые реально использует services.py
    mocker.patch("parcels.services.cache.get", return_value=None)
    mocker.patch("parcels.services.cache.set")

    mock_response = mocker.Mock()
    mock_response.json.return_value = {"Valute": {"USD": {"Value": 90.5}}}
    mock_response.raise_for_status.return_value = None
    mocker.patch("parcels.services.httpx2.get", return_value=mock_response)

    rate = get_usd_rub_rate()
    assert isinstance(rate, Decimal)
    assert rate == Decimal("90.5")


@pytest.mark.django_db
def test_get_usd_rub_rate_from_cache(mocker: MockerFixture) -> None:
    """Если курс в кэше — HTTP-запрос не делается."""

    # Кэш отдаёт значение — сеть не должна вызываться
    mocker.patch("django.core.cache.cache.get", return_value="88.0")
    mock_get = mocker.patch("httpx.get")

    rate = get_usd_rub_rate()
    assert rate == Decimal("88.0")
    mock_get.assert_not_called()


@pytest.mark.django_db
def test_calculate_delivery_cost_formula(
    parcel_type: ParcelType,
    mocker: MockerFixture,
) -> None:
    """Формула: (weight * 0.5 + content_cost_usd * 0.01) * rate."""

    # Фиксируем курс, чтобы результат был предсказуемым
    mocker.patch("parcels.services.get_usd_rub_rate", return_value=Decimal("100"))

    parcel = Parcel.objects.create(
        name="Куртка",
        weight=Decimal("2.5"),
        type=parcel_type,
        content_cost_usd=Decimal("160"),
        session_key="test-session",
    )

    cost = calculate_delivery_cost(parcel)

    # (2.5 * 0.5 + 160 * 0.01) * 100 = (1.25 + 1.6) * 100 = 285
    assert cost == Decimal("285.00")
