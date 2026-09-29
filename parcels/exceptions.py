from typing import Any

from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Приводит все ошибки DRF к единому формату."""
    response = exception_handler(exc, context)

    # DRF не знает это исключение — пробрасываем дальше (Django обработает)
    if response is None:
        return None

    # Оборачиваем стандартный ответ DRF в единый формат
    error_data = {
        "error": {
            "code": "ERROR",
            "message": str(exc),
            "details": response.data,
        }
    }

    response.data = error_data
    return response
