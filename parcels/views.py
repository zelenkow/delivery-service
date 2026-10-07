import logging
from datetime import date

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
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
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from parcels.filters import ParcelFilter
from parcels.models import Parcel, ParcelType
from parcels.mongo import aggregate_delivery_costs_by_type
from parcels.rag.generator import generate_answer
from parcels.rag.retriever import search_knowledge
from parcels.serializers import (
    DeliveryCostsReportQuerySerializer,
    DeliveryCostsReportSerializer,
    ParcelAssignSerializer,
    ParcelCreateSerializer,
    ParcelDetailSerializer,
    ParcelListSerializer,
    ParcelTypeSerializer,
    SupportAskSerializer,
)
from parcels.utils import get_session_key, get_user_parcels

logger = logging.getLogger(__name__)


class SupportAskThrottle(AnonRateThrottle):
    """Более жёсткий лимит для RAG — защита бюджета LLM."""

    scope = "support"


class ParcelViewSet(viewsets.ModelViewSet[Parcel]):
    """CRUD для посылок."""

    # Базовый queryset (переопределяется в get_queryset — фильтр по сессии)
    queryset = Parcel.objects.all()

    # Сериализатор по умолчанию (переопределяется в get_serializer_class)
    serializer_class = ParcelCreateSerializer

    # Бэкенд фильтрации — django-filter
    filter_backends = [DjangoFilterBackend]

    # Класс фильтра: параметры type и has_delivery_cost
    filterset_class = ParcelFilter

    def get_queryset(self) -> QuerySet[Parcel]:
        """Только посылки текущей сессии."""

        # select_related — избегаем N+1 при обращении к type.name
        return get_user_parcels(self.request).select_related("type")

    def get_serializer_class(self) -> type[serializers.BaseSerializer[Parcel]]:
        """Выбор сериализатора в зависимости от действия."""

        # list — краткий, retrieve — полный, create — для записи
        if self.action == "list":
            return ParcelListSerializer
        # retrieve — детали с полным набором полей
        if self.action == "retrieve":
            return ParcelDetailSerializer
        # create/update/destroy — сериализатор для записи
        return ParcelCreateSerializer

    def create(self, request: Request) -> Response:
        """Регистрация посылки."""

        # Валидация входящих данных и создание с привязкой к сессии
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # session_key гарантирует изоляцию посылок по пользователю
        session_key = get_session_key(request)
        parcel = serializer.save(session_key=session_key)

        # По ТЗ возвращаем только id созданной посылки
        return Response({"id": parcel.id}, status=status.HTTP_201_CREATED)


class ParcelTypeViewSet(viewsets.ReadOnlyModelViewSet[ParcelType]):
    """Справочник типов посылок (только чтение)."""

    # ReadOnlyModelViewSet — только list и retrieve, без create/update
    queryset = ParcelType.objects.all()
    serializer_class = ParcelTypeSerializer


class SupportAskView(APIView):
    """RAG-эндпоинт: вопрос → ответ."""

    serializer_class = SupportAskSerializer
    throttle_classes = [SupportAskThrottle]

    def post(self, request: Request) -> Response:
        """Принимает вопрос, ищет контекст в векторной БД, генерирует ответ через LLM."""

        # Валидация вопроса (не пустой, до 1000 символов)
        serializer = SupportAskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["question"]

        # Поиск в векторной БД: сетевые ошибки → 503, ошибки сервера → 502
        try:
            chunks = search_knowledge(question)
        # ResponseHandlingException — сетевая ошибка (connection refused, timeout)
        except ResponseHandlingException as e:
            logger.error("Qdrant недоступен: %s", e)
            return Response(
                {"error": {"code": "SERVICE_UNAVAILABLE", "message": "Векторная БД недоступна"}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        # UnexpectedResponse — Qdrant ответил с ошибкой (4xx/5xx)
        except UnexpectedResponse as e:
            logger.error("Qdrant вернул ошибку %s: %s", e.status_code, e)
            return Response(
                {"error": {"code": "VECTOR_DB_ERROR", "message": "Ошибка векторной БД"}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Генерация ответа: различаем rate limit, timeout, connection, API
        try:
            answer = generate_answer(question, chunks)
        # ModelRateLimitError — LLM перегружена или лимит запросов
        except ModelRateLimitError as e:
            logger.error("DeepSeek rate limit: %s", e)
            return Response(
                {"error": {"code": "LLM_UNAVAILABLE", "message": "LLM перегружена"}},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        # ModelTimeoutError — LLM не ответила за отведённое время
        except ModelTimeoutError as e:
            logger.error("DeepSeek timeout: %s", e)
            return Response(
                {"error": {"code": "LLM_TIMEOUT", "message": "LLM не ответила вовремя"}},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        # ModelConnectionError — не удалось установить соединение с LLM
        except ModelConnectionError as e:
            logger.error("DeepSeek connection error: %s", e)
            return Response(
                {"error": {"code": "LLM_UNAVAILABLE", "message": "LLM недоступна"}},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        # ModelAPIError — прочие ошибки API (невалидный ключ, 5xx)
        except ModelAPIError as e:
            logger.error("DeepSeek API error: %s", e)
            return Response(
                {"error": {"code": "LLM_ERROR", "message": "Ошибка LLM"}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Успешный ответ — только текст от LLM
        return Response({"answer": answer})


class ParcelAssignView(APIView):
    """Привязка посылки к транспортной компании."""

    serializer_class = ParcelAssignSerializer

    def post(self, request: Request, pk: str) -> Response:
        """Атомарно закрепляет посылку за первой обратившейся компанией."""

        # Валидация company_id (целое, ≥ 1)
        serializer = ParcelAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company_id = serializer.validated_data["company_id"]

        # Атомарный UPDATE: только если company_id ещё NULL
        updated = Parcel.objects.filter(pk=pk, company_id__isnull=True).update(
            company_id=company_id
        )

        # updated=1 — компания успела первой
        if updated == 1:
            return Response({"company_id": company_id}, status=status.HTTP_200_OK)

        # Либо посылки нет, либо уже привязана
        parcel = Parcel.objects.filter(pk=pk).first()
        # Посылки с таким id нет — 404
        if parcel is None:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Посылка не найдена"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Посылка уже занята другой компанией — 409 с текущим company_id
        return Response(
            {
                "error": {
                    "code": "CONFLICT",
                    "message": "Посылка уже привязана",
                    "company_id": parcel.company_id,
                }
            },
            status=status.HTTP_409_CONFLICT,
        )


class DeliveryCostsReportView(APIView):
    """Отчёт: сумма delivery_cost по типам за день."""

    # Описание эндпоинта для Swagger: query-параметр date + схема ответа
    @extend_schema(
        # date — обязательный query-параметр формата YYYY-MM-DD
        parameters=[
            OpenApiParameter(
                name="date",
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                required=True,
            ),
        ],
        # Схема ответа 200: date + report[] (type_id, type_name, total)
        responses={200: DeliveryCostsReportSerializer},
    )
    def get(self, request: Request) -> Response:
        """Принимает YYYY-MM-DD, возвращает суммы по типам."""

        # Валидация query-параметра date
        query = DeliveryCostsReportQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        target_date: date = query.validated_data["date"]

        # Агрегация в Mongo (Decimal128 → Decimal уже сделан)
        rows = aggregate_delivery_costs_by_type(target_date)

        # Сериализация ответа (date + список строк отчёта)
        serializer = DeliveryCostsReportSerializer({"date": target_date, "report": rows})
        return Response(serializer.data, status=status.HTTP_200_OK)
