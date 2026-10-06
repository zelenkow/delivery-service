import logging

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore

from parcels.rag.embeddings import FastEmbedWrapper

logger = logging.getLogger(__name__)

COLLECTION_NAME = "knowledge"
QDRANT_URL = "http://localhost:6333"
EMBEDDING_MODEL = "minishlab/potion-multilingual-128M"
TOP_K = 5


def get_vectorstore() -> QdrantVectorStore:
    """Возвращает подключение к коллекции Qdrant."""

    embeddings = FastEmbedWrapper(model_name="minishlab/potion-multilingual-128M")
    return QdrantVectorStore.from_existing_collection(
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        url=QDRANT_URL,
    )


def search_knowledge(question: str, top_k: int = TOP_K) -> list[Document]:
    """Ищет top-K релевантных чанков по вопросу."""

    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search(question, k=top_k)
    logger.info("Найдено %s чанков по вопросу: %s", len(results), question[:50])
    return results
