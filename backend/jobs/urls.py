from django.urls import path

from . import views

urlpatterns = [
    path("jobs/", views.JobListView.as_view(), name="job-list"),
    path("jobs/discover/", views.DiscoverView.as_view(), name="job-discover"),
    path("jobs/discovery-runs/", views.DiscoveryRunListView.as_view(), name="discovery-run-list"),
    path("jobs/discovery-runs/<uuid:pk>/", views.DiscoveryRunDetailView.as_view(), name="discovery-run-detail"),
    path("jobs/<uuid:pk>/", views.JobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:pk>/verify/", views.JobVerifyView.as_view(), name="job-verify"),
    path("job-sources/", views.JobSourceListView.as_view(), name="job-source-list"),
    path("job-sources/<uuid:pk>/", views.JobSourceDetailView.as_view(), name="job-source-detail"),
]