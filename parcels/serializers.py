from decimal import Decimal
from typing import Any

from rest_framework import serializers

from parcels.models import Parcel, ParcelType
from parcels.utils import format_delivery_cost


class ParcelCreateSerializer(serializers.ModelSerializer[Parcel]):
    """Сериализатор для создания посылки."""

    # Принимаем только id типа, не вложенный объект
    type = serializers.PrimaryKeyRelatedField(queryset=ParcelType.objects.all())

    class Meta:
        model = Parcel
        fields = ["name", "weight", "type", "content_cost_usd"]

    def validate_weight(self, value: Decimal) -> Decimal:
        """Вес должен быть положительным."""

        if value <= 0:
            raise serializers.ValidationError("Вес должен быть больше 0")
        return value

    def validate_content_cost_usd(self, value: Decimal) -> Decimal:
        """Стоимсоть не должна быть отрицательной"""
        if value < 0:
            raise serializers.ValidationError("Стоимость не может быть отрицательной")
        return value


class ParcelTypeSerializer(serializers.ModelSerializer[ParcelType]):
    """Сериализатор типа посылки."""

    class Meta:
        model = ParcelType
        fields = ["id", "name", "code"]


class ParcelListSerializer(serializers.ModelSerializer[Parcel]):
    """Сериализатор для списка посылок."""

    # Отдаём имя типа вместо id — удобно для UI
    type = serializers.CharField(source="type.name")

    # Может быть None → «Не рассчитано»
    delivery_cost = serializers.SerializerMethodField()

    class Meta:
        model = Parcel
        fields = ["id", "name", "weight", "type", "content_cost_usd", "delivery_cost"]

    def get_delivery_cost(self, obj: Parcel) -> str | Decimal:
        return format_delivery_cost(obj)


class ParcelDetailSerializer(serializers.ModelSerializer[Parcel]):
    """Сериализатор деталей посылки."""

    type = serializers.CharField(source="type.name")
    delivery_cost = serializers.SerializerMethodField()

    class Meta:
        model = Parcel
        fields = [
            "id",
            "name",
            "weight",
            "type",
            "content_cost_usd",
            "delivery_cost",
            "delivery_cost_calculated_at",
            "company_id",
            "created_at",
        ]

    def get_delivery_cost(self, obj: Parcel) -> str | Decimal:
        return format_delivery_cost(obj)


class SupportAskSerializer(serializers.Serializer[Any]):
    """Сериализатор вопроса службе поддержки."""

    # Текст вопроса: не пустой, до 1000 символов
    question = serializers.CharField(max_length=1000, allow_blank=False)


class ParcelAssignSerializer(serializers.Serializer[Any]):
    """Сериализатор привязки посылки к компании."""

    # ID компании: положительное целое
    company_id = serializers.IntegerField(min_value=1)


class DeliveryCostsReportQuerySerializer(serializers.Serializer[Any]):
    """Query-параметры отчёта по стоимостям доставок."""

    # Дата отчёта в формате YYYY-MM-DD
    date = serializers.DateField()


class DeliveryCostsReportItemSerializer(serializers.Serializer[Any]):
    """Одна строка отчёта: тип + сумма."""

    # ID типа посылки
    type_id = serializers.IntegerField()
    # Название типа (одежда/электроника/разное)
    type_name = serializers.CharField()
    # Сумма delivery_cost за день по типу
    total = serializers.DecimalField(max_digits=14, decimal_places=2)


class DeliveryCostsReportSerializer(serializers.Serializer[Any]):
    """Ответ отчёта: дата + список строк."""

    # Дата отчёта
    date = serializers.DateField()
    # Строки отчёта: по одной на каждый тип
    report = DeliveryCostsReportItemSerializer(many=True)
