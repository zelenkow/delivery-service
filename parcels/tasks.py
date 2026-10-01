import logging

from celery import shared_task
from django.utils import timezone

from parcels.models import Parcel
from parcels.services import calculate_delivery_cost

logger = logging.getLogger(__name__)


@shared_task
def calculate_delivery_costs() -> int:
    """Периодическая задача: считает стоимость для посылок без неё."""

    parcels = Parcel.objects.filter(delivery_cost__isnull=True)
    count = 0

    for parcel in parcels:
        cost = calculate_delivery_cost(parcel)
        parcel.delivery_cost = cost
        parcel.delivery_cost_calculated_at = timezone.now()
        parcel.save(update_fields=["delivery_cost", "delivery_cost_calculated_at"])

        count += 1

    logger.info("Рассчитано стоимостей: %s", count)

    return count
