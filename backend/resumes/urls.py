from django.urls import path

from . import views

urlpatterns = [
    path("resumes/upload/", views.ResumeUploadView.as_view(), name="resume-upload"),
    path("resumes/active/", views.ActiveResumeView.as_view(), name="resume-active"),
    path("resumes/", views.ResumeListView.as_view(), name="resume-list"),
    path("resumes/<uuid:pk>/", views.ResumeDetailView.as_view(), name="resume-detail"),
    path("resumes/<uuid:pk>/activate/", views.ResumeActivateView.as_view(), name="resume-activate"),
    path("resumes/<uuid:pk>/reprocess/", views.ResumeReprocessView.as_view(), name="resume-reprocess"),
    path("resumes/<uuid:pk>/facts/", views.ResumeFactsView.as_view(), name="resume-facts"),
    path("resume-facts/<uuid:pk>/", views.ResumeFactDetailView.as_view(), name="resume-fact-detail"),
]