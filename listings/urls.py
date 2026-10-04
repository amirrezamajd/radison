from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("panel/login/", views.panel_login, name="panel_login"),
    path("panel/register/", views.panel_register, name="panel_register"),
    path("panel/", views.panel, name="panel"),
    path("panel/extract/", views.panel_extract, name="panel_extract"),
    path("panel/delete/<int:pk>/", views.panel_delete, name="panel_delete"),
    path("panel/logout/", views.panel_logout, name="panel_logout"),
]
