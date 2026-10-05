from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("listings.urls")),
]

# Serve project static files in production too (WhiteNoise + explicit fallback).
# django.conf.urls.static.static() is DEBUG-only, so we wire this ourselves.
urlpatterns += [
    re_path(
        r"^static/(?P<path>.*)$",
        serve,
        {"document_root": str(settings.STATICFILES_DIRS[0])},
    ),
]

if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": str(settings.MEDIA_ROOT)},
        )
    ]
