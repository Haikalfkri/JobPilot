from django.urls import path

from . import views

urlpatterns = [
    path("settings/search-preferences/", views.SearchPreferencesView.as_view(), name="search-preferences"),
    path("matching/jobs/<uuid:job_id>/analyze/", views.AnalyzeJobView.as_view(), name="match-analyze"),
    path("matching/results/", views.MatchResultListView.as_view(), name="match-list"),
    path("matching/results/<uuid:pk>/", views.MatchResultDetailView.as_view(), name="match-detail"),
    path("matching/recalculate/", views.RecalculateView.as_view(), name="match-recalculate"),
]