from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from parcels.filters import ParcelFilter
from parcels.models import Parcel, ParcelType
from parcels.serializers import (
    ParcelCreateSerializer,
    ParcelDetailSerializer,
    ParcelListSerializer,
    ParcelTypeSerializer,
)
from parcels.utils import get_session_key, get_user_parcels


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

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_key = get_session_key(request)
        parcel = serializer.save(session_key=session_key)

        return Response({"id": parcel.id}, status=status.HTTP_201_CREATED)


class ParcelTypeViewSet(viewsets.ReadOnlyModelViewSet[ParcelType]):
    """Справочник типов посылок (только чтение)."""

    queryset = ParcelType.objects.all()
    serializer_class = ParcelTypeSerializer
