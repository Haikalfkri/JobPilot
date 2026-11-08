from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

urlpatterns = [
    path("api/v1/", include("core.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]