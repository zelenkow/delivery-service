from django.urls import path
from rest_framework.routers import DefaultRouter

from parcels.views import ParcelTypeViewSet, ParcelViewSet, SupportAskView

router = DefaultRouter()
router.register("parcels", ParcelViewSet, basename="parcel")
router.register("parcel-types", ParcelTypeViewSet, basename="parcel-type")

urlpatterns = [
    path("support/ask/", SupportAskView.as_view(), name="support-ask"),
    *router.urls,
]
