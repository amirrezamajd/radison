from django.db import models


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
