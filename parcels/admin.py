from django.contrib import admin

from parcels.models import Parcel, ParcelType


@admin.register(ParcelType)
class ParcelTypeAdmin(admin.ModelAdmin[ParcelType]):
    list_display = ["id", "name", "code", "created_at"]
    search_fields = ["name", "code"]


@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin[Parcel]):
    list_display = ["id", "name", "weight", "type", "delivery_cost", "created_at"]
    list_filter = ["type", "delivery_cost"]
    search_fields = ["name", "session_key"]
    readonly_fields = ["id", "created_at", "updated_at"]
