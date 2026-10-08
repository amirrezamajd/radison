from django.contrib.sitemaps.views import sitemap
from django.urls import path, re_path

from . import panel_views, views
from .sitemaps import SITEMAPS

urlpatterns = [
    path("", views.home, name="home"),
    path("properties/", views.properties, name="properties"),
    path("property/<int:pk>/", views.property_detail, name="property_detail"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("panel/login/", views.panel_login, name="panel_login"),
    path("panel/register/", views.panel_register, name="panel_register"),
    path("panel/", views.panel, name="panel"),
    path("panel/properties/", views.panel_properties, name="panel_properties"),
    path("panel/stats/", panel_views.panel_stats, name="panel_stats"),
    path("panel/pin/<int:pk>/", panel_views.panel_pin, name="panel_pin"),
    path("panel/backups/", panel_views.panel_backups, name="panel_backups"),
    path("panel/backups/create/", panel_views.panel_backup_create, name="panel_backup_create"),
    path("panel/backups/full.zip", panel_views.panel_media_download, name="panel_media_download"),
    path("panel/backups/<str:name>", panel_views.panel_backup_download, name="panel_backup_download"),
    path("panel/extract/", views.panel_extract, name="panel_extract"),
    path("panel/reextract/<int:pk>/", views.panel_reextract, name="panel_reextract"),
    path("panel/tours/upload/", views.panel_tour_upload, name="panel_tour_upload"),
    path("panel/tours/delete/<int:pk>/", views.panel_tour_delete, name="panel_tour_delete"),
    path("panel/assign-tour/<int:pk>/", views.panel_assign_tour, name="panel_assign_tour"),
    path("panel/delete/<int:pk>/", views.panel_delete, name="panel_delete"),
    path("panel/logout/", views.panel_logout, name="panel_logout"),
    path("api/properties/<int:pk>/view/", views.track_property_view, name="track_property_view"),
    path("api/properties/<int:pk>/whatsapp/", views.track_whatsapp_click, name="track_property_whatsapp"),
    path("api/whatsapp/", views.track_whatsapp_click, name="track_whatsapp"),
    path("api/traffic-source/", views.track_traffic_source, name="track_traffic_source"),
    path("tours/<slug:slug>/", views.virtual_tour_index, name="virtual_tour_index"),
    re_path(
        r"^tours/(?P<slug>[-a-zA-Z0-9_]+)/(?P<path>.+)$",
        views.virtual_tour_file,
        name="virtual_tour_file",
    ),
]
