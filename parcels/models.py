import uuid

from django.db import models


class ParcelType(models.Model):
    """Справочник типов посылок."""

    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class Parcel(models.Model):
    """Посылка, зарегистрированная пользователем."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    weight = models.DecimalField(max_digits=10, decimal_places=3)
    type = models.ForeignKey(
        ParcelType,
        on_delete=models.PROTECT,
        related_name="parcels",
    )
    content_cost_usd = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    delivery_cost_calculated_at = models.DateTimeField(null=True, blank=True)
    session_key = models.CharField(max_length=64, db_index=True)
    company_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session_key"], name="parcel_session_idx"),
            models.Index(fields=["type"], name="parcel_type_idx"),
            models.Index(fields=["company_id"], name="parcel_company_idx"),
            models.Index(
                fields=["id"],
                name="parcel_no_cost_idx",
                condition=models.Q(delivery_cost__isnull=True),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"
