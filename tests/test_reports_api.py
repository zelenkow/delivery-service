from decimal import Decimal

import pytest
from pytest_mock import MockerFixture
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_report_success(api_client: APIClient, mocker: MockerFixture) -> None:
    """Отчёт возвращает 200 и корректную структуру."""

    # Мокаем агрегацию в Mongo — она уже протестирована отдельно
    mocker.patch(
        "parcels.views.aggregate_delivery_costs_by_type",
        return_value=[
            {"type_id": 1, "type_name": "одежда", "total": Decimal("244.28")},
            {"type_id": 2, "type_name": "электроника", "total": Decimal("4371.29")},
        ],
    )

    response = api_client.get("/api/reports/delivery-costs/?date=2026-10-07")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["date"] == "2026-10-07"
    assert len(response.data["report"]) == 2
    assert response.data["report"][0]["type_name"] == "одежда"
    assert response.data["report"][0]["total"] == "244.28"


@pytest.mark.django_db
def test_report_missing_date(api_client: APIClient) -> None:
    """Без параметра date → 400."""

    response = api_client.get("/api/reports/delivery-costs/")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_report_invalid_date(api_client: APIClient) -> None:
    """Невалидная дата → 400."""

    response = api_client.get("/api/reports/delivery-costs/?date=not-a-date")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_report_empty_day(api_client: APIClient, mocker: MockerFixture) -> None:
    """Нет данных за день → 200 с пустым report."""

    mocker.patch("parcels.views.aggregate_delivery_costs_by_type", return_value=[])

    response = api_client.get("/api/reports/delivery-costs/?date=2020-01-01")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["report"] == []
