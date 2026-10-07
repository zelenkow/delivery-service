import logging
from pathlib import Path

from django.conf import settings
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from parcels.rag.embeddings import FastEmbedWrapper

logger = logging.getLogger(__name__)

COLLECTION_NAME = "knowledge"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def build_knowledge_base(file_path: Path) -> int:
    """Строит базу знаний через LangChain + FastEmbed."""

    text = file_path.read_text(encoding="utf-8")
    docs = [Document(page_content=text, metadata={"source": str(file_path)})]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    embeddings = FastEmbedWrapper(model_name="minishlab/potion-multilingual-128M")

    QdrantVectorStore.from_documents(
        chunks,
        embeddings,
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection_name=COLLECTION_NAME,
        force_recreate=True,
    )

    logger.info("Загружено %s чанков из %s", len(chunks), file_path.name)
    return len(chunks)
