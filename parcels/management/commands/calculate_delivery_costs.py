from typing import Any

from django.core.management.base import BaseCommand

from parcels.tasks import calculate_delivery_costs


class Command(BaseCommand):
    """Ручной запуск расчёта стоимости доставки."""

    help = "Рассчитывает стоимость доставки для посылок без неё"

    def handle(self, *args: Any, **options: Any) -> None:
        count = calculate_delivery_costs()
        self.stdout.write(self.style.SUCCESS(f"Рассчитано: {count}"))
