from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ServiceUnavailable

from . import selectors, services
from .models import DiscoveryRun, Job, JobSource
from .serializers import (
    DiscoveryRunSerializer, DiscoverRequestSerializer, JobDetailSerializer, JobFilterSerializer,
    JobListSerializer, JobSourceSerializer,
)
from .tasks import verify_job_task


class JobListView(generics.ListAPIView):
    serializer_class = JobListSerializer

    def get_queryset(self):
        filters = JobFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return selectors.filter_jobs(filters.validated_data)


class JobDetailView(generics.RetrieveAPIView):
    queryset = Job.objects.prefetch_related("listings__source")
    serializer_class = JobDetailSerializer


class JobVerifyView(APIView):
    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk)
        try:
            verify_job_task.delay(str(job.id))
        except Exception:  # noqa: BLE001 - broker down
            raise ServiceUnavailable() from None
        return Response({"job_id": str(job.id), "status": "queued"}, status=status.HTTP_202_ACCEPTED)


class DiscoverView(APIView):
    def post(self, request):
        serializer = DiscoverRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        run = services.start_discovery(**serializer.validated_data)
        return Response({"discovery_run_id": str(run.id), "status": run.status},
                        status=status.HTTP_202_ACCEPTED)


class DiscoveryRunListView(generics.ListAPIView):
    queryset = DiscoveryRun.objects.prefetch_related("source_runs__source")
    serializer_class = DiscoveryRunSerializer


class DiscoveryRunDetailView(generics.RetrieveAPIView):
    queryset = DiscoveryRun.objects.prefetch_related("source_runs__source")
    serializer_class = DiscoveryRunSerializer


class JobSourceListView(generics.ListAPIView):
    serializer_class = JobSourceSerializer
    pagination_class = None

    def get_queryset(self):
        services.sync_sources()
        return JobSource.objects.all()


class JobSourceDetailView(generics.UpdateAPIView):
    queryset = JobSource.objects.all()
    serializer_class = JobSourceSerializer
    http_method_names = ["patch", "options"]