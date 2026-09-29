import logging
import time
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Логирует метод, путь, статус, длительность и session_key."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Замер до обработки
        start = time.perf_counter()

        response = self.get_response(request)

        # Замер после обработки
        duration_ms = (time.perf_counter() - start) * 1000

        # Сессия может отсутствовать, если SessionMiddleware не подключён
        session_key = None
        if hasattr(request, "session"):
            session_key = request.session.session_key

        # Логируем запрос: метод, путь, статус, длительность, session_key
        logger.info(
            "%s %s %s %.2fms session=%s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            session_key or "-",
        )

        return response
