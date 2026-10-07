from typing import Any

import pytest
from django.test import Client
from pytest_mock import MockerFixture
from rest_framework.test import APIClient
from rest_framework.throttling import AnonRateThrottle

from parcels.models import ParcelType


@pytest.fixture(autouse=True)
def disable_throttling(mocker: MockerFixture) -> None:
    """Отключает throttling во всех тестах — не нужен Redis."""

    mocker.patch.object(AnonRateThrottle, "allow_request", return_value=True)


@pytest.fixture
def api_client() -> APIClient:
    """DRF-клиент для тестов API."""

    return APIClient()


@pytest.fixture
def parcel_type(db: Any) -> ParcelType:
    """Тип посылки для тестов."""

    obj, _ = ParcelType.objects.get_or_create(
        code="clothes",
        defaults={"name": "одежда"},
    )
    return obj


@pytest.fixture
def django_client() -> Client:
    """Django-клиент (для сессий)."""

    return Client()
