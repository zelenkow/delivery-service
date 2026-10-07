from typing import Any

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from parcels.models import Parcel, ParcelType


@pytest.fixture
def parcel(db: Any, parcel_type: ParcelType) -> Parcel:
    """Посылка без привязанной компании."""

    # Свободная посылка: company_id=None
    return Parcel.objects.create(
        name="Куртка",
        weight="2.5",
        type=parcel_type,
        content_cost_usd="120.00",
        session_key="test-session",
    )


@pytest.mark.django_db
def test_assign_success(api_client: APIClient, parcel: Parcel) -> None:
    """Свободная посылка → 200, company_id проставлен."""

    # Первая компания привязывает посылку
    response = api_client.post(
        f"/api/parcels/{parcel.id}/assign/",
        {"company_id": 42},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["company_id"] == 42

    # Проверяем, что значение сохранилось в БД
    parcel.refresh_from_db()
    assert parcel.company_id == 42


@pytest.mark.django_db
def test_assign_conflict(api_client: APIClient, parcel: Parcel) -> None:
    """Уже привязана → 409 + текущий company_id."""

    # Первая компания заняла посылку
    parcel.company_id = 42
    parcel.save(update_fields=["company_id"])

    # Вторая компания получает 409 и видит, кто занял
    response = api_client.post(
        f"/api/parcels/{parcel.id}/assign/",
        {"company_id": 99},
        format="json",
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["error"]["code"] == "CONFLICT"
    assert response.data["error"]["company_id"] == 42

    # company_id не перезаписан
    parcel.refresh_from_db()
    assert parcel.company_id == 42


@pytest.mark.django_db
def test_assign_not_found(api_client: APIClient) -> None:
    """Несуществующая посылка → 404."""

    # UUID валидный, но посылки нет
    response = api_client.post(
        "/api/parcels/00000000-0000-0000-0000-000000000000/assign/",
        {"company_id": 42},
        format="json",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.data["error"]["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_assign_invalid_company_id(api_client: APIClient, parcel: Parcel) -> None:
    """company_id ≤ 0 → 400."""

    # min_value=1 в сериализаторе
    response = api_client.post(
        f"/api/parcels/{parcel.id}/assign/",
        {"company_id": 0},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_assign_missing_company_id(api_client: APIClient, parcel: Parcel) -> None:
    """Нет company_id → 400."""

    response = api_client.post(
        f"/api/parcels/{parcel.id}/assign/",
        {},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_assign_second_company_does_not_overwrite(
    api_client: APIClient,
    parcel: Parcel,
) -> None:
    """Вторая компания не перезаписывает первую (проверка атомарности)."""

    # Компания A — успех
    api_client.post(
        f"/api/parcels/{parcel.id}/assign/",
        {"company_id": 1},
        format="json",
    )

    # Компания B — должна получить 409, а не перезаписать
    response = api_client.post(
        f"/api/parcels/{parcel.id}/assign/",
        {"company_id": 2},
        format="json",
    )
    assert response.status_code == status.HTTP_409_CONFLICT

    # В БД остаётся компания A
    parcel.refresh_from_db()
    assert parcel.company_id == 1
