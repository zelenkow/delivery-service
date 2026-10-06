from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from parcels.rag.builder import build_knowledge_base


class Command(BaseCommand):
    """Строит базу знаний через LangChain + FastEmbed."""

    help = "Загружает customs_rules.txt в Qdrant через LangChain"

    def handle(self, *args: Any, **options: Any) -> None:
        file_path = Path(settings.BASE_DIR) / "parcels" / "knowledge" / "customs_rules.txt"
        count = build_knowledge_base(file_path)
        self.stdout.write(self.style.SUCCESS(f"Загружено: {count} чанков"))
