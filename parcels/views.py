import logging

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from langchain_core.exceptions import (
    ModelAPIError,
    ModelConnectionError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from rest_framework import serializers, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from parcels.filters import ParcelFilter
from parcels.models import Parcel, ParcelType
from parcels.rag.generator import generate_answer
from parcels.rag.retriever import search_knowledge
from parcels.serializers import (
    ParcelCreateSerializer,
    ParcelDetailSerializer,
    ParcelListSerializer,
    ParcelTypeSerializer,
    SupportAskSerializer,
)
from parcels.utils import get_session_key, get_user_parcels

logger = logging.getLogger(__name__)


class ParcelViewSet(viewsets.ModelViewSet[Parcel]):
    """CRUD для посылок."""

    queryset = Parcel.objects.all()
    serializer_class = ParcelCreateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ParcelFilter

    def get_queryset(self) -> QuerySet[Parcel]:
        """Только посылки текущей сессии."""

        # select_related — избегаем N+1 при обращении к type.name
        return get_user_parcels(self.request).select_related("type")

    def get_serializer_class(self) -> type[serializers.BaseSerializer[Parcel]]:
        """Выбор сериализатора в зависимости от действия"""

        # list — краткий, retrieve — полный, create — для записи
        if self.action == "list":
            return ParcelListSerializer
        if self.action == "retrieve":
            return ParcelDetailSerializer
        return ParcelCreateSerializer

    def create(self, request: Request) -> Response:
        """Регистрация посылки."""

        # Валидация входящих данных и создание с привязкой к сессии
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # session_key гарантирует изоляцию посылок по пользователю
        session_key = get_session_key(request)
        parcel = serializer.save(session_key=session_key)

        return Response({"id": parcel.id}, status=status.HTTP_201_CREATED)


class ParcelTypeViewSet(viewsets.ReadOnlyModelViewSet[ParcelType]):
    """Справочник типов посылок (только чтение)."""

    # ReadOnlyModelViewSet — только list и retrieve, без create/update
    queryset = ParcelType.objects.all()
    serializer_class = ParcelTypeSerializer


class SupportAskView(APIView):
    """RAG-эндпоинт: вопрос → ответ."""

    serializer_class = SupportAskSerializer

    def post(self, request: Request) -> Response:
        """Принимает вопрос, ищет контекст в векторной БД, генерирует ответ через LLM."""

        # Валидация вопроса (не пустой, до 1000 символов)
        serializer = SupportAskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["question"]

        # Поиск в векторной БД: сетевые ошибки → 503, ошибки сервера → 502
        try:
            chunks = search_knowledge(question)
        except ResponseHandlingException as e:
            logger.error("Qdrant недоступен: %s", e)
            return Response(
                {"error": {"code": "SERVICE_UNAVAILABLE", "message": "Векторная БД недоступна"}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except UnexpectedResponse as e:
            logger.error("Qdrant вернул ошибку %s: %s", e.status_code, e)
            return Response(
                {"error": {"code": "VECTOR_DB_ERROR", "message": "Ошибка векторной БД"}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Генерация ответа: различаем rate limit, timeout, connection, API
        try:
            answer = generate_answer(question, chunks)
        except ModelRateLimitError as e:
            logger.error("DeepSeek rate limit: %s", e)
            return Response(
                {"error": {"code": "LLM_UNAVAILABLE", "message": "LLM перегружена"}},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ModelTimeoutError as e:
            logger.error("DeepSeek timeout: %s", e)
            return Response(
                {"error": {"code": "LLM_TIMEOUT", "message": "LLM не ответила вовремя"}},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except ModelConnectionError as e:
            logger.error("DeepSeek connection error: %s", e)
            return Response(
                {"error": {"code": "LLM_UNAVAILABLE", "message": "LLM недоступна"}},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ModelAPIError as e:
            logger.error("DeepSeek API error: %s", e)
            return Response(
                {"error": {"code": "LLM_ERROR", "message": "Ошибка LLM"}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"answer": answer})
