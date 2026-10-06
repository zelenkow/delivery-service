import logging
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

COLLECTION_NAME = "knowledge"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
QDRANT_URL = "http://localhost:6333"


def build_knowledge_base(file_path: Path) -> int:
    """Строит базу знаний через LangChain + FastEmbed."""

    loader = TextLoader(str(file_path), encoding="utf-8")
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    embeddings = FastEmbedEmbeddings(model_name="minishlab/potion-multilingual-128M")

    QdrantVectorStore.from_documents(
        chunks,
        embeddings,
        url=QDRANT_URL,
        collection_name=COLLECTION_NAME,
        force_recreate=True,
    )

    logger.info("Загружено %s чанков из %s", len(chunks), file_path.name)
    return len(chunks)
