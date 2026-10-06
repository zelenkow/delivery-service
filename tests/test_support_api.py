import pytest
from pytest_mock import MockerFixture
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_support_ask_success(api_client: APIClient, mocker: MockerFixture) -> None:
    """RAG-эндпоинт возвращает answer от LLM."""

    # Мокаем retriever и generator — внешние зависимости (Qdrant, LLM)
    mocker.patch("parcels.views.search_knowledge", return_value=[])
    mocker.patch("parcels.views.generate_answer", return_value="Да, ноутбук можно отправить.")

    response = api_client.post(
        "/api/support/ask/",
        {"question": "Можно ли отправить ноутбук?"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["answer"] == "Да, ноутбук можно отправить."


@pytest.mark.django_db
def test_support_ask_empty_question(api_client: APIClient) -> None:
    """Пустой вопрос → 400."""

    # Сериализатор не пропускает пустую строку
    response = api_client.post(
        "/api/support/ask/",
        {"question": ""},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_support_ask_missing_question(api_client: APIClient) -> None:
    """Отсутствует question → 400."""

    # Пустое тело — question обязателен
    response = api_client.post("/api/support/ask/", {}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_support_ask_qdrant_unavailable(api_client: APIClient, mocker: MockerFixture) -> None:
    """Qdrant недоступен → 503."""

    from qdrant_client.http.exceptions import ResponseHandlingException

    # ResponseHandlingException оборачивает исходное исключение
    mocker.patch(
        "parcels.views.search_knowledge",
        side_effect=ResponseHandlingException(Exception("connection refused")),
    )

    response = api_client.post(
        "/api/support/ask/",
        {"question": "Можно ли отправить ноутбук?"},
        format="json",
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.data["error"]["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.django_db
def test_support_ask_llm_timeout(api_client: APIClient, mocker: MockerFixture) -> None:
    """Таймаут LLM → 504."""

    from langchain_core.exceptions import ModelTimeoutError

    # Ошибка приходит из generate_answer — мокаем его
    mocker.patch("parcels.views.search_knowledge", return_value=[])
    mocker.patch(
        "parcels.views.generate_answer",
        side_effect=ModelTimeoutError("timeout"),
    )

    response = api_client.post(
        "/api/support/ask/",
        {"question": "Можно ли отправить ноутбук?"},
        format="json",
    )
    assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    assert response.data["error"]["code"] == "LLM_TIMEOUT"
