from django.apps import AppConfig


class ListingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "listings"
    verbose_name = "املاک رادیسون"

    def ready(self):
        from django.contrib import admin

        admin.site.site_header = "رادیسون · مدیریت"
        admin.site.site_title = "Radison Admin"
        admin.site.index_title = "پنل مدیریت جنگو"
