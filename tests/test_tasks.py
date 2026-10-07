from decimal import Decimal
from typing import Any

import pytest
from pytest_mock import MockerFixture

from parcels.models import Parcel, ParcelType
from parcels.tasks import calculate_delivery_costs


@pytest.fixture
def parcel_type(db: Any) -> ParcelType:
    """Тип посылки для тестов задач."""

    # Тип создаётся через get_or_create — безопасно при повторных запусках
    obj, _ = ParcelType.objects.get_or_create(
        code="clothes",
        defaults={"name": "одежда"},
    )
    return obj


@pytest.mark.django_db
def test_task_calculates_costs_for_parcels_without_cost(
    parcel_type: ParcelType,
    mocker: MockerFixture,
) -> None:
    """Таска проставляет стоимость только посылкам с delivery_cost IS NULL."""

    # Фиксируем курс — без обращения к Redis и CBR
    mocker.patch("parcels.tasks.get_usd_rub_rate", return_value=Decimal("100"))
    # Мокаем запись в Mongo — не пишем в реальную БД в тестах
    log_mock = mocker.patch("parcels.tasks.log_delivery_costs_bulk", return_value=2)

    # Две посылки без стоимости
    Parcel.objects.create(
        name="Куртка",
        weight=Decimal("2"),
        type=parcel_type,
        content_cost_usd=Decimal("100"),
        session_key="s1",
    )
    Parcel.objects.create(
        name="Футболка",
        weight=Decimal("1"),
        type=parcel_type,
        content_cost_usd=Decimal("50"),
        session_key="s1",
    )

    count = calculate_delivery_costs()

    # Обе посылки обработаны
    assert count == 2

    # Стоимость рассчитана по формуле: (2*0.5 + 100*0.01) * 100 = 200
    first = Parcel.objects.get(name="Куртка")
    assert first.delivery_cost == Decimal("200.00")
    assert first.delivery_cost_calculated_at is not None

    # Запись в Mongo вызвана один раз (один батч)
    log_mock.assert_called_once()


@pytest.mark.django_db
def test_task_skips_parcels_with_existing_cost(
    parcel_type: ParcelType,
    mocker: MockerFixture,
) -> None:
    """Таска не трогает посылки, у которых стоимость уже рассчитана."""

    mocker.patch("parcels.tasks.get_usd_rub_rate", return_value=Decimal("100"))
    log_mock = mocker.patch("parcels.tasks.log_delivery_costs_bulk")

    # Посылка уже со стоимостью — не должна попасть в обработку
    Parcel.objects.create(
        name="Готовая",
        weight=Decimal("2"),
        type=parcel_type,
        content_cost_usd=Decimal("100"),
        session_key="s1",
        delivery_cost=Decimal("999.00"),
    )

    count = calculate_delivery_costs()

    # Ничего не обработано
    assert count == 0

    # В Mongo не писали — батч пустой
    log_mock.assert_not_called()


@pytest.mark.django_db
def test_task_returns_zero_for_empty_queryset(mocker: MockerFixture) -> None:
    """Пустая выборка → 0, без падений."""

    mocker.patch("parcels.tasks.get_usd_rub_rate", return_value=Decimal("100"))
    log_mock = mocker.patch("parcels.tasks.log_delivery_costs_bulk")

    count = calculate_delivery_costs()

    assert count == 0
    log_mock.assert_not_called()


@pytest.mark.django_db
def test_task_writes_correct_log_documents(
    parcel_type: ParcelType,
    mocker: MockerFixture,
) -> None:
    """В Mongo уходит правильный набор полей документа."""

    mocker.patch("parcels.tasks.get_usd_rub_rate", return_value=Decimal("90"))
    log_mock = mocker.patch("parcels.tasks.log_delivery_costs_bulk", return_value=1)

    parcel = Parcel.objects.create(
        name="Куртка",
        weight=Decimal("2.5"),
        type=parcel_type,
        content_cost_usd=Decimal("120"),
        session_key="s1",
    )

    calculate_delivery_costs()

    # Забираем документы, переданные в log_delivery_costs_bulk
    docs = log_mock.call_args.args[0]
    assert len(docs) == 1
    doc = docs[0]
    assert doc["parcel_id"] == str(parcel.id)
    assert doc["type_id"] == parcel_type.pk
    assert doc["type_name"] == "одежда"

    # Decimal128 при сравнении приводится к Decimal
    assert doc["delivery_cost"].to_decimal() == Decimal("220.5")
