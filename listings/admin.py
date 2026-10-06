from django.contrib import admin, messages
from django.utils import timezone

from .models import AdminJoinRequest, Property, PropertyImage, VirtualTour


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


@admin.register(VirtualTour)
class VirtualTourAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("slug", "storage_dir", "created_at")


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("title", "price_text", "property_type", "deal_type", "virtual_tour", "updated_at")
    search_fields = ("title", "source_token", "source_url")
    list_filter = ("virtual_tour",)
    autocomplete_fields = ("virtual_tour",)
    inlines = [PropertyImageInline]

    def delete_model(self, request, obj):
        self._delete_image_files(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._delete_image_files(obj)
        super().delete_queryset(request, queryset)

    @staticmethod
    def _delete_image_files(property_obj):
        for image in property_obj.images.all():
            if image.image:
                image.image.delete(save=False)


@admin.register(AdminJoinRequest)
class AdminJoinRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "username", "phone", "status", "created_at", "reviewed_at")
    list_filter = ("status", "created_at")
    search_fields = ("full_name", "phone", "user__username")
    actions = ("approve_requests", "reject_requests")
    readonly_fields = ("user", "created_at", "reviewed_at")

    @admin.display(description="نام کاربری")
    def username(self, obj):
        return obj.user.username

    @admin.action(description="تأیید و فعال‌سازی دسترسی پنل")
    def approve_requests(self, request, queryset):
        approved = 0
        for item in queryset.exclude(status=AdminJoinRequest.Status.APPROVED):
            user = item.user
            user.is_active = True
            user.is_staff = True
            user.save(update_fields=["is_active", "is_staff"])
            item.status = AdminJoinRequest.Status.APPROVED
            item.reviewed_at = timezone.now()
            item.save(update_fields=["status", "reviewed_at"])
            approved += 1
        self.message_user(request, f"{approved} درخواست تأیید شد.", messages.SUCCESS)

    @admin.action(description="رد درخواست")
    def reject_requests(self, request, queryset):
        rejected = 0
        for item in queryset.exclude(status=AdminJoinRequest.Status.REJECTED):
            user = item.user
            user.is_active = False
            user.is_staff = False
            user.save(update_fields=["is_active", "is_staff"])
            item.status = AdminJoinRequest.Status.REJECTED
            item.reviewed_at = timezone.now()
            item.save(update_fields=["status", "reviewed_at"])
            rejected += 1
        self.message_user(request, f"{rejected} درخواست رد شد.", messages.WARNING)
