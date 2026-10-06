from typing import cast

from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings


class FastEmbedWrapper(Embeddings):
    """Обёртка над fastembed.TextEmbedding с интерфейсом LangChain Embeddings."""

    def __init__(self, model_name: str) -> None:
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Векторизует документы (чанки)."""

        embeddings = self._model.embed(texts)
        return [cast(list[float], e.tolist()) for e in embeddings]

    def embed_query(self, text: str) -> list[float]:
        """Векторизует вопрос."""

        embedding = next(iter(self._model.query_embed(text)))
        return cast(list[float], embedding.tolist())
