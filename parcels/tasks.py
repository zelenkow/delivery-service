import logging
from datetime import UTC
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from parcels.models import Parcel
from parcels.mongo import log_delivery_costs_bulk, to_decimal128
from parcels.services import compute_delivery_cost, get_usd_rub_rate

logger = logging.getLogger(__name__)


@shared_task
def calculate_delivery_costs() -> int:
    """Периодическая задача: считает стоимость для посылок без неё."""

    # Получаем курс
    rate = get_usd_rub_rate()

    # Фиксируем время
    calculated_at = timezone.now()

    # Для Mongo — naive UTC datetime (ISODate)
    calculated_at_utc = calculated_at.astimezone(UTC).replace(tzinfo=None)

    parcels = (
        Parcel.objects.filter(delivery_cost__isnull=True)
        .select_related("type")
        .iterator(chunk_size=settings.DELIVERY_COST_BATCH_SIZE)
    )

    batch: list[Parcel] = []
    log_docs: list[dict[str, Any]] = []
    count = 0

    for parcel in parcels:
        parcel.delivery_cost = compute_delivery_cost(parcel, rate)
        parcel.delivery_cost_calculated_at = calculated_at
        batch.append(parcel)

        # Документ для Mongo
        log_docs.append(
            {
                "parcel_id": str(parcel.id),
                "type_id": parcel.type.pk,
                "type_name": parcel.type.name,
                "weight": to_decimal128(parcel.weight),
                "content_cost_usd": to_decimal128(parcel.content_cost_usd),
                "usd_rub_rate": to_decimal128(rate),
                "delivery_cost": to_decimal128(parcel.delivery_cost),
                "calculated_at": calculated_at_utc,
            }
        )

        # Раз в BATCH_SIZE — bulk_update + insert_many
        if len(batch) >= settings.DELIVERY_COST_BATCH_SIZE:
            Parcel.objects.bulk_update(
                batch,
                ["delivery_cost", "delivery_cost_calculated_at"],
            )
            log_delivery_costs_bulk(log_docs)
            count += len(batch)
            batch.clear()
            log_docs.clear()

    # Хвост — остаток, который не добрал до BATCH_SIZE
    if batch:
        Parcel.objects.bulk_update(
            batch,
            ["delivery_cost", "delivery_cost_calculated_at"],
        )
        log_delivery_costs_bulk(log_docs)
        count += len(batch)

    logger.info("Рассчитано стоимостей: %s", count)

    return count
