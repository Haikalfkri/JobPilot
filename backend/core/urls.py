from django.urls import path

from . import views

urlpatterns = [
    path("system/health/", views.health, name="system-health"),
]