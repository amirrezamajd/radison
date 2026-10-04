from django.conf import settings
from django.db import models


class AdminJoinRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار تأیید"
        APPROVED = "approved", "تأیید شده"
        REJECTED = "rejected", "رد شده"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_join_request",
    )
    full_name = models.CharField("نام و نام خانوادگی", max_length=120)
    phone = models.CharField("شماره تماس", max_length=20, blank=True)
    note = models.TextField("توضیحات", blank=True)
    status = models.CharField(
        "وضعیت",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "درخواست عضویت ادمین"
        verbose_name_plural = "درخواست‌های عضویت ادمین"

    def __str__(self):
        return f"{self.full_name} ({self.user.username}) - {self.get_status_display()}"


class Property(models.Model):
    source_url = models.URLField(unique=True)
    source_token = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    price_text = models.CharField(max_length=120, blank=True)
    price_per_meter_text = models.CharField(max_length=120, blank=True)
    property_type = models.CharField(max_length=80, blank=True)
    deal_type = models.CharField(max_length=80, blank=True)
    specs = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "ملک"
        verbose_name_plural = "ملک‌ها"

    def __str__(self):
        return self.title

    @property
    def cover_image(self):
        image = self.images.order_by("order").first()
        return image.image.url if image else ""


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="properties/%Y/%m/")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.property.title} - تصویر {self.order + 1}"
