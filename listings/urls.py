from django.urls import path, re_path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("properties/", views.properties, name="properties"),
    path("panel/login/", views.panel_login, name="panel_login"),
    path("panel/register/", views.panel_register, name="panel_register"),
    path("panel/", views.panel, name="panel"),
    path("panel/properties/", views.panel_properties, name="panel_properties"),
    path("panel/extract/", views.panel_extract, name="panel_extract"),
    path("panel/reextract/<int:pk>/", views.panel_reextract, name="panel_reextract"),
    path("panel/tours/upload/", views.panel_tour_upload, name="panel_tour_upload"),
    path("panel/tours/delete/<int:pk>/", views.panel_tour_delete, name="panel_tour_delete"),
    path("panel/assign-tour/<int:pk>/", views.panel_assign_tour, name="panel_assign_tour"),
    path("panel/delete/<int:pk>/", views.panel_delete, name="panel_delete"),
    path("panel/logout/", views.panel_logout, name="panel_logout"),
    path("api/properties/<int:pk>/view/", views.track_property_view, name="track_property_view"),
    path("tours/<slug:slug>/", views.virtual_tour_index, name="virtual_tour_index"),
    re_path(
        r"^tours/(?P<slug>[-a-zA-Z0-9_]+)/(?P<path>.+)$",
        views.virtual_tour_file,
        name="virtual_tour_file",
    ),
]
