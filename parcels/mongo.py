import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Any

from bson.decimal128 import Decimal128
from django.conf import settings
from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

logger = logging.getLogger(__name__)


COLLECTION_NAME = "delivery_cost_log"


@lru_cache(maxsize=1)
def get_client() -> MongoClient[dict[str, Any]]:
    """Возвращает singleton-клиент MongoDB."""

    return MongoClient(
        host=settings.MONGO_HOST,
        port=settings.MONGO_PORT,
        username=settings.MONGO_USER,
        password=settings.MONGO_PASSWORD,
        authSource="admin",
    )


def get_db() -> Database[dict[str, Any]]:
    """Возвращает БД для логов расчётов."""

    return get_client()[settings.MONGO_DB]


def get_collection() -> Collection[dict[str, Any]]:
    """Возвращает коллекцию логов расчётов."""

    return get_db()[COLLECTION_NAME]


def ensure_indexes() -> None:
    """Создаёт индексы для агрегации по дням и типам."""

    collection = get_collection()
    collection.create_index(
        [("calculated_at", ASCENDING), ("type_id", ASCENDING)],
        name="idx_calculated_at_type_id",
    )


def log_delivery_costs_bulk(docs: list[dict[str, Any]]) -> int:
    """Пишет пачку логов расчётов. Возвращает количество вставленных."""

    if not docs:
        return 0

    result = get_collection().insert_many(docs, ordered=False)
    logger.info("Записано в Mongo логов расчётов: %s", len(result.inserted_ids))
    return len(result.inserted_ids)


def to_decimal128(value: Decimal | float | int) -> Decimal128:
    """Конвертирует значение в Decimal128 для MongoDB."""

    return Decimal128(str(value))


def _to_decimal(value: Any) -> Decimal:
    """Приводит Decimal128 или число к Decimal."""

    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))


def aggregate_delivery_costs_by_type(target_date: date) -> list[dict[str, Any]]:
    """Сумма delivery_cost по типам за указанный день (UTC)."""

    # Границы дня в UTC: [00:00, следующий 00:00)
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=UTC)
    end = start + timedelta(days=1)

    # Pipeline: фильтр по дню → группировка по type_id → сортировка
    pipeline: list[dict[str, Any]] = [
        {
            "$match": {
                "calculated_at": {
                    "$gte": start.replace(tzinfo=None),
                    "$lt": end.replace(tzinfo=None),
                }
            }
        },
        {
            "$group": {
                "_id": "$type_id",
                "type_name": {"$first": "$type_name"},
                "total": {"$sum": "$delivery_cost"},
            }
        },
        {
            "$project": {
                "type_name": 1,
                "total": {"$round": ["$total", 2]},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    results = get_collection().aggregate(pipeline)

    # Приводим _id → type_id, для чистого ответа API
    return [
        {"type_id": doc["_id"], "type_name": doc["type_name"], "total": _to_decimal(doc["total"])}
        for doc in results
    ]
