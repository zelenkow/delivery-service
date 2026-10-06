import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Имя коллекции в Qdrant и endpoint
COLLECTION_NAME = "knowledge"
QDRANT_URL = "http://localhost:6333"

# Путь к снапшоту рядом с модулем — работает независимо от CWD
SNAPSHOT_PATH = Path(__file__).parent / "snapshots" / "knowledge.snapshot"


def load_from_snapshot() -> None:
    """Загружает снапшот коллекции knowledge в Qdrant."""

    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Снапшот не найден: {SNAPSHOT_PATH}")

    # Qdrant принимает снапшот как multipart-загрузку
    url = f"{QDRANT_URL}/collections/{COLLECTION_NAME}/snapshots/upload"

    # Открывает файл в бинарном режиме и отправляет как multipart
    with SNAPSHOT_PATH.open("rb") as f:
        files = {"snapshot": (SNAPSHOT_PATH.name, f, "application/octet-stream")}
        response = httpx.post(url, files=files, timeout=60)
        response.raise_for_status()

    logger.info("Снапшот загружен: %s", SNAPSHOT_PATH.name)
