from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Property


class StaticPagesSitemap(Sitemap):
    changefreq = "daily"

    def items(self):
        return ["home", "properties"]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == "home" else 0.9


class PropertySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Property.objects.order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    "pages": StaticPagesSitemap,
    "properties": PropertySitemap,
}
