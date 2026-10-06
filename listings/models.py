import builtins
from urllib.parse import quote

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from .images import optimize_upload
from .parsing import parse_area, parse_bedrooms, parse_price


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


class VirtualTour(models.Model):
    name = models.CharField("نام بازدید مجازی", max_length=200)
    slug = models.SlugField("شناسه URL", max_length=120, unique=True)
    storage_dir = models.CharField("پوشه ذخیره‌سازی", max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "بازدید مجازی"
        verbose_name_plural = "بازدیدهای مجازی"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("virtual_tour_index", kwargs={"slug": self.slug})

    @property
    def absolute_folder(self):
        return settings.MEDIA_ROOT / "virtual-tours" / self.storage_dir

    @staticmethod
    def make_unique_slug(name: str) -> str:
        base = slugify(name) or "tour"
        base = base[:100]
        slug = base
        counter = 2
        while VirtualTour.objects.filter(slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        return slug


class Property(models.Model):
    source_url = models.URLField(unique=True)
    source_token = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    price_text = models.CharField(max_length=120, blank=True)
    price_per_meter_text = models.CharField(max_length=120, blank=True)
    property_type = models.CharField(max_length=80, blank=True)
    deal_type = models.CharField(max_length=80, blank=True)
    specs = models.JSONField(default=list, blank=True)
    virtual_tour = models.ForeignKey(
        VirtualTour,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="properties",
        verbose_name="بازدید مجازی",
    )
    view_count = models.PositiveIntegerField("تعداد بازدید", default=0, db_index=True)
    price_value = models.BigIntegerField("قیمت (تومان)", null=True, blank=True, db_index=True)
    area_value = models.PositiveIntegerField("متراژ", null=True, blank=True, db_index=True)
    bedrooms = models.PositiveSmallIntegerField("تعداد خواب", null=True, blank=True)
    pin_order = models.PositiveIntegerField(
        "ترتیب در ابتدای صفحه اصلی",
        null=True,
        blank=True,
        db_index=True,
        help_text="خالی = عادی. ملک‌های دارای عدد، به ترتیب اول صفحه اصلی نمایش داده می‌شوند.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "ملک"
        verbose_name_plural = "ملک‌ها"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.refresh_derived_fields()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"price_value", "area_value", "bedrooms"}
        super().save(*args, **kwargs)

    def refresh_derived_fields(self):
        self.price_value = parse_price(self.price_text)
        self.area_value = parse_area(self.specs)
        self.bedrooms = parse_bedrooms(self.specs)

    def get_absolute_url(self):
        return reverse("property_detail", kwargs={"pk": self.pk})

    @property
    def code(self):
        return str(self.pk)

    def whatsapp_url(self, page_url: str = "") -> str:
        text = f"سلام، درباره ملک کد {self.code} «{self.title}» در سایت رادیسون سؤال دارم."
        if page_url:
            text += f"\n{page_url}"
        return f"https://wa.me/{settings.RADISON_WHATSAPP}?text={quote(text)}"

    @property
    def cover_image(self):
        image = self.images.order_by("order").first()
        return image.image.url if image else ""

    @property
    def virtual_tour_url(self):
        if self.virtual_tour_id:
            return self.virtual_tour.get_absolute_url()
        return ""


    @property
    def is_pinned(self):
        return self.pin_order is not None

    @property
    def cover_thumbnail(self):
        image = self.images.order_by("order").first()
        return image.thumb_url if image else ""


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="properties/%Y/%m/")
    thumbnail = models.ImageField(upload_to="properties/thumbs/%Y/%m/", blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.property.title} - تصویر {self.order + 1}"

    @builtins.property
    def thumb_url(self):
        if self.thumbnail:
            return self.thumbnail.url
        return self.image.url if self.image else ""

    def save(self, *args, **kwargs):
        if self.image and not self.image._committed:
            optimized = optimize_upload(self.image)
            if optimized:
                self.image, self.thumbnail = optimized
        super().save(*args, **kwargs)

    def delete_files(self):
        for field in (self.image, self.thumbnail):
            if field:
                field.delete(save=False)


class PropertyEvent(models.Model):
    class Kind(models.TextChoices):
        VIEW = "view", "بازدید ملک"
        WHATSAPP = "whatsapp", "کلیک واتساپ"

    property = models.ForeignKey(
        Property,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="events",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "رویداد ملک"
        verbose_name_plural = "رویدادهای ملک"


class PageVisit(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=255)
    source = models.CharField("منبع", max_length=120, db_index=True)
    referrer_host = models.CharField(max_length=255, blank=True)
    device = models.CharField(max_length=20, blank=True)
    visitor_id = models.CharField(max_length=32, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "بازدید صفحه"
        verbose_name_plural = "بازدیدهای صفحه"
