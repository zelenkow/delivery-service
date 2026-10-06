import logging

from django.conf import settings
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Промпт: LLM отвечает только на основе найденного контекста
PROMPT_TEMPLATE = """
Ты — служба поддержки службы доставки посылок.
Отвечай на вопрос пользователя, используя только контекст ниже.
Если в контексте нет ответа — скажи, что не знаешь.

Контекст:
{context}

Вопрос: {question}

Ответ:
"""


def get_llm() -> ChatOpenAI:
    """Возвращает клиент DeepSeek через OpenAI-совместимый API."""

    # temperature=0.2 — точные ответы без фантазий
    # timeout=30 — защита от зависания сети
    # max_retries=2 — повторы при 429/5xx
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        base_url=settings.DEEPSEEK_API_URL,
        api_key=settings.DEEPSEEK_API_KEY,
        temperature=0.2,
        timeout=30,
        max_retries=2,
    )


def generate_answer(question: str, chunks: list[Document]) -> str:
    """Генерирует ответ на основе вопроса и найденных чанков."""

    # Склеиваем тексты чанков через пустую строку
    context = "\n\n".join(doc.page_content for doc in chunks)

    # Цепочка LCEL: шаблон → LLM → парсер строки
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | get_llm() | StrOutputParser()

    # Запуск цепочки с подстановкой переменных в шаблон
    answer = chain.invoke({"context": context, "question": question})

    logger.info("Сгенерирован ответ (%s символов)", len(answer))
    return answer
