from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ServiceUnavailable
from jobs.models import Job

from . import services
from .models import JobMatch
from .serializers import (
    MatchDetailSerializer, MatchFilterSerializer, MatchSerializer, SearchPreferenceSerializer,
)
from .tasks import analyze_job_task, refresh_matches_task


class SearchPreferencesView(APIView):
    def get(self, request):
        return Response(SearchPreferenceSerializer(services.get_preferences()).data)

    def put(self, request):
        prefs = services.get_preferences()
        serializer = SearchPreferenceSerializer(prefs, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        try:  # preferences change every score: refresh in the background (best effort)
            refresh_matches_task.delay()
        except Exception:  # noqa: BLE001
            pass
        return Response(serializer.data)


class AnalyzeJobView(APIView):
    def post(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id)
        services.require_candidate()  # fail fast with a clear message
        try:
            analyze_job_task.delay(str(job.id), True)
        except Exception:  # noqa: BLE001 - broker down
            raise ServiceUnavailable() from None
        return Response({"job_id": str(job.id), "status": "queued"}, status=status.HTTP_202_ACCEPTED)


class RecalculateView(APIView):
    def post(self, request):
        services.require_candidate()
        try:
            refresh_matches_task.delay(True)
        except Exception:  # noqa: BLE001
            raise ServiceUnavailable() from None
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)


class MatchResultListView(generics.ListAPIView):
    serializer_class = MatchSerializer

    def get_queryset(self):
        filters = MatchFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        params = filters.validated_data
        queryset = JobMatch.objects.filter(master_resume__is_active=True).select_related("job")
        if "job_id" in params:
            queryset = queryset.filter(job_id=params["job_id"])
        if "min_score" in params:
            queryset = queryset.filter(overall_score__gte=params["min_score"])
        if "eligibility_status" in params:
            queryset = queryset.filter(eligibility_status=params["eligibility_status"])
        return queryset.order_by(params.get("ordering", "-overall_score"))


class MatchResultDetailView(generics.RetrieveAPIView):
    queryset = JobMatch.objects.select_related("job")
    serializer_class = MatchDetailSerializer