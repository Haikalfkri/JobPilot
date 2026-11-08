from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import MasterResume, ResumeFact
from .serializers import (
    FactCreateSerializer,
    FactUpdateSerializer,
    MasterResumeSerializer,
    ResumeFactSerializer,
    ResumeUploadSerializer,
)


class ResumeUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        serializer = ResumeUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resume, duplicate_of = services.create_master_resume(serializer.validated_data["file"])
        body = MasterResumeSerializer(resume).data
        body["duplicate_of_version"] = duplicate_of
        return Response(body, status=status.HTTP_201_CREATED)


class ResumeListView(generics.ListAPIView):
    queryset = MasterResume.objects.all()
    serializer_class = MasterResumeSerializer


class ActiveResumeView(APIView):
    def get(self, request):
        resume = MasterResume.objects.filter(is_active=True).first()
        if resume is None:
            raise NotFound("There is no active resume yet.")
        return Response(MasterResumeSerializer(resume).data)


class ResumeDetailView(generics.RetrieveAPIView):
    queryset = MasterResume.objects.all()
    serializer_class = MasterResumeSerializer


class ResumeActivateView(APIView):
    def post(self, request, pk):
        resume = services.activate_resume(get_object_or_404(MasterResume, pk=pk))
        return Response(MasterResumeSerializer(resume).data)


class ResumeReprocessView(APIView):
    def post(self, request, pk):
        resume = services.reprocess_resume(get_object_or_404(MasterResume, pk=pk))
        return Response(MasterResumeSerializer(resume).data, status=status.HTTP_202_ACCEPTED)


class FactPagination(PageNumberPagination):
    page_size = 500
    page_size_query_param = "page_size"


class ResumeFactsView(generics.ListCreateAPIView):
    serializer_class = ResumeFactSerializer
    pagination_class = FactPagination

    def get_queryset(self):
        resume = get_object_or_404(MasterResume, pk=self.kwargs["pk"])
        queryset = resume.facts.all()
        for param, field in (("category", "category"), ("status", "verification_status")):
            value = self.request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})
        return queryset

    def create(self, request, *args, **kwargs):
        resume = get_object_or_404(MasterResume, pk=self.kwargs["pk"])
        serializer = FactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fact = services.create_fact(resume, serializer.validated_data)
        return Response(ResumeFactSerializer(fact).data, status=status.HTTP_201_CREATED)


class ResumeFactDetailView(APIView):
    def patch(self, request, pk):
        fact = get_object_or_404(ResumeFact, pk=pk)
        serializer = FactUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fact = services.update_fact(fact, serializer.validated_data)
        return Response(ResumeFactSerializer(fact).data)