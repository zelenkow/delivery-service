import pytest
from rest_framework import status
from rest_framework.test import APIClient

from parcels.models import Parcel, ParcelType


@pytest.mark.django_db
def test_create_parcel_success(api_client: APIClient, parcel_type: ParcelType) -> None:
    """Создание посылки возвращает 201 и id."""

    # Отправляем валидные данные — ожидаем 201 и id в ответе
    response = api_client.post(
        "/api/parcels/",
        {"name": "Куртка", "weight": "2.5", "type": parcel_type.pk, "content_cost_usd": "120.00"},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert "id" in response.data
    assert Parcel.objects.count() == 1


@pytest.mark.django_db
def test_create_parcel_invalid_weight(api_client: APIClient, parcel_type: ParcelType) -> None:
    """Вес ≤ 0 → 400."""

    # Вес 0 — кастомная валидация сериализатора должна вернуть 400
    response = api_client.post(
        "/api/parcels/",
        {"name": "Куртка", "weight": "0", "type": parcel_type.pk, "content_cost_usd": "120.00"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Parcel.objects.count() == 0


@pytest.mark.django_db
def test_create_parcel_unknown_type(api_client: APIClient) -> None:
    """Несуществующий тип → 400."""

    # PrimaryKeyRelatedField проверяет существование типа в queryset
    response = api_client.post(
        "/api/parcels/",
        {"name": "Куртка", "weight": "2.5", "type": 9999, "content_cost_usd": "120.00"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_list_parcels_only_own(api_client: APIClient, parcel_type: ParcelType) -> None:
    """Список возвращает только посылки текущей сессии."""

    # Создаём посылку в сессии A
    api_client.post(
        "/api/parcels/",
        {"name": "Куртка", "weight": "2.5", "type": parcel_type.pk, "content_cost_usd": "120.00"},
        format="json",
    )

    # Другой клиент = другая сессия — не должен видеть чужую посылку
    other_client = APIClient()
    response = other_client.get("/api/parcels/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 0


@pytest.mark.django_db
def test_retrieve_own_parcel(api_client: APIClient, parcel_type: ParcelType) -> None:
    """Детали своей посылки — 200."""

    # Создаём посылку и забираем её id
    create_response = api_client.post(
        "/api/parcels/",
        {"name": "Куртка", "weight": "2.5", "type": parcel_type.pk, "content_cost_usd": "120.00"},
        format="json",
    )
    parcel_id = create_response.data["id"]

    # Запрашиваем детали по id — ожидаем 200 и имя из запроса
    response = api_client.get(f"/api/parcels/{parcel_id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Куртка"


@pytest.mark.django_db
def test_retrieve_foreign_parcel(api_client: APIClient, parcel_type: ParcelType) -> None:
    """Чужая посылка — 404."""

    # Создаём посылку в сессии A
    create_response = api_client.post(
        "/api/parcels/",
        {"name": "Куртка", "weight": "2.5", "type": parcel_type.pk, "content_cost_usd": "120.00"},
        format="json",
    )
    parcel_id = create_response.data["id"]

    # Другая сессия не должна видеть чужую посылку → 404 (не 403, чтобы не палить существование)
    other_client = APIClient()
    response = other_client.get(f"/api/parcels/{parcel_id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_filter_by_type(api_client: APIClient, parcel_type: ParcelType) -> None:
    """Фильтр ?type= возвращает только посылки этого типа."""

    # Одна посылка типа "одежда"
    api_client.post(
        "/api/parcels/",
        {"name": "Куртка", "weight": "2.5", "type": parcel_type.pk, "content_cost_usd": "120.00"},
        format="json",
    )

    # Фильтр по тому же типу — должна быть 1 посылка
    response = api_client.get(f"/api/parcels/?type={parcel_type.pk}")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_filter_by_delivery_cost(api_client: APIClient, parcel_type: ParcelType) -> None:
    """Фильтр ?has_delivery_cost=false возвращает только без стоимости."""

    # Новая посылка — delivery_cost ещё None
    api_client.post(
        "/api/parcels/",
        {"name": "Куртка", "weight": "2.5", "type": parcel_type.pk, "content_cost_usd": "120.00"},
        format="json",
    )

    # Фильтр по отсутствию стоимости — должна быть 1 посылка
    response = api_client.get("/api/parcels/?has_delivery_cost=false")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_list_parcel_types(api_client: APIClient, parcel_type: ParcelType) -> None:
    """Справочник типов доступен."""

    # Тип создаётся фикстурой — в ответе должен быть хотя бы один
    response = api_client.get("/api/parcel-types/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) >= 1
