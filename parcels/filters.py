import django_filters
from django.db.models import QuerySet

from parcels.models import Parcel


class ParcelFilter(django_filters.FilterSet):
    """Фильтр посылок по типу и наличию стоимости."""

    type = django_filters.NumberFilter(field_name="type_id")
    has_delivery_cost = django_filters.BooleanFilter(method="filter_has_delivery_cost")

    class Meta:
        model = Parcel
        fields = ["type", "has_delivery_cost"]

    def filter_has_delivery_cost(
        self,
        queryset: QuerySet[Parcel],
        name: str,
        value: bool,
    ) -> QuerySet[Parcel]:
        if value:
            return queryset.filter(delivery_cost__isnull=False)
        return queryset.filter(delivery_cost__isnull=True)
