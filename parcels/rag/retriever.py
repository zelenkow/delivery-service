import logging
from functools import lru_cache

from django.conf import settings
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore

from parcels.rag.embeddings import FastEmbedWrapper

logger = logging.getLogger(__name__)

COLLECTION_NAME = "knowledge"
EMBEDDING_MODEL = "minishlab/potion-multilingual-128M"
TOP_K = 5

# Singleton
_embeddings = FastEmbedWrapper(model_name=EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_vectorstore() -> QdrantVectorStore:
    """Возвращает подключение к коллекции Qdrant (кэшируется)."""

    return QdrantVectorStore.from_existing_collection(
        embedding=_embeddings,
        collection_name=COLLECTION_NAME,
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_READ_ONLY_API_KEY,
    )


def search_knowledge(question: str, top_k: int = TOP_K) -> list[Document]:
    """Ищет top-K релевантных чанков по вопросу."""

    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search(question, k=top_k)
    logger.info("Найдено %s чанков по вопросу: %s", len(results), question[:50])
    return results
