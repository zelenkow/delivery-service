from django.db.models import QuerySet
from django.http import HttpRequest

from parcels.models import Parcel


def get_session_key(request: HttpRequest) -> str:
    """Возвращает session_key, создавая сессию при необходимости."""

    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    assert session_key is not None
    return session_key


def get_user_parcels(request: HttpRequest) -> QuerySet[Parcel]:
    """Возвращает queryset посылок текущей сессии."""
    session_key = get_session_key(request)
    return Parcel.objects.filter(session_key=session_key)
