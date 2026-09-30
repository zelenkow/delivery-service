from rest_framework.routers import DefaultRouter

from parcels.views import ParcelTypeViewSet, ParcelViewSet

router = DefaultRouter()
router.register("parcels", ParcelViewSet, basename="parcel")
router.register("parcel-types", ParcelTypeViewSet, basename="parcel-type")

urlpatterns = router.urls
