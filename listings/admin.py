from django.contrib import admin

from .models import Property, PropertyImage


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("title", "price_text", "property_type", "deal_type", "updated_at")
    search_fields = ("title", "source_token", "source_url")
    inlines = [PropertyImageInline]
