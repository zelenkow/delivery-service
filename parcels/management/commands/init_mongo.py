from typing import Any

from django.core.management.base import BaseCommand

from parcels.mongo import ensure_indexes


class Command(BaseCommand):
    """Создаёт индексы в MongoDB."""

    help = "Инициализирует индексы MongoDB для логов расчётов"

    def handle(self, *args: Any, **options: Any) -> None:
        ensure_indexes()
        self.stdout.write(self.style.SUCCESS("Индексы MongoDB созданы"))
