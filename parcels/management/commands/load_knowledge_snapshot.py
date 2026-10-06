from typing import Any

from django.core.management.base import BaseCommand

from parcels.rag.loader import load_from_snapshot


class Command(BaseCommand):
    """Загружает снапшот в Qdrant (без модели)."""

    help = "Загружает knowledge.snapshot в Qdrant"

    def handle(self, *args: Any, **options: Any) -> None:
        load_from_snapshot()
        self.stdout.write(self.style.SUCCESS("Снапшот загружен"))
