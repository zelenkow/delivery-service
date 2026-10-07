from django.urls import path
from rest_framework.routers import DefaultRouter

from parcels.views import (
    DeliveryCostsReportView,
    ParcelAssignView,
    ParcelTypeViewSet,
    ParcelViewSet,
    SupportAskView,
)

router = DefaultRouter()
router.register("parcels", ParcelViewSet, basename="parcel")
router.register("parcel-types", ParcelTypeViewSet, basename="parcel-type")

urlpatterns = [
    path("parcels/<uuid:pk>/assign/", ParcelAssignView.as_view(), name="parcel-assign"),
    path("support/ask/", SupportAskView.as_view(), name="support-ask"),
    path(
        "reports/delivery-costs/", DeliveryCostsReportView.as_view(), name="reports-delivery-costs"
    ),
    *router.urls,
]
