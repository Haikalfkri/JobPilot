from rest_framework import serializers

from .models import (
    DiscoveryRun, EmploymentType, ExperienceLevel, Job, JobSource, JobSourceListing, JobStatus,
    RemoteEligibility, SourceRun, WorkArrangement,
)


class ListingSerializer(serializers.ModelSerializer):
    source_key = serializers.CharField(source="source.key", read_only=True)
    source_name = serializers.CharField(source="source.display_name", read_only=True)

    class Meta:
        model = JobSourceListing
        fields = ["source_key", "source_name", "original_url", "first_seen_at", "last_seen_at",
                  "last_checked_at", "source_status"]
        read_only_fields = fields


class JobListSerializer(serializers.ModelSerializer):
    sources = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = ["id", "title", "company_name", "location_text", "country_code", "work_arrangement",
                  "remote_eligibility", "eligible_countries", "employment_type", "experience_level",
                  "salary_min", "salary_max", "salary_currency", "published_at", "discovered_at",
                  "last_verified_at", "status", "sources"]
        read_only_fields = fields

    def get_sources(self, job) -> list[dict]:
        return [{"source_key": l.source.key, "source_name": l.source.display_name,
                 "original_url": l.original_url} for l in job.listings.all()]


class JobDetailSerializer(JobListSerializer):
    listings = ListingSerializer(many=True, read_only=True)

    class Meta(JobListSerializer.Meta):
        fields = JobListSerializer.Meta.fields + ["description", "listings"]
        read_only_fields = fields


class JobFilterSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, max_length=100)
    country_code = serializers.CharField(required=False, min_length=2, max_length=2)
    work_arrangement = serializers.ChoiceField(required=False, choices=WorkArrangement.choices)
    remote_eligibility = serializers.ChoiceField(required=False, choices=RemoteEligibility.choices)
    employment_type = serializers.ChoiceField(required=False, choices=EmploymentType.choices)
    experience_level = serializers.ChoiceField(required=False, choices=ExperienceLevel.choices)
    status = serializers.ChoiceField(required=False, choices=JobStatus.choices)
    source = serializers.CharField(required=False, max_length=50)
    published_within_days = serializers.IntegerField(required=False, min_value=1, max_value=3650)
    ordering = serializers.ChoiceField(
        required=False, choices=["published_at", "-published_at", "discovered_at", "-discovered_at"])


class DiscoverRequestSerializer(serializers.Serializer):
    source_keys = serializers.ListField(child=serializers.CharField(max_length=50), required=False,
                                        allow_empty=False, max_length=20)
    keywords = serializers.ListField(child=serializers.CharField(max_length=50, allow_blank=True),
                                     required=False, max_length=50)


class SourceRunSerializer(serializers.ModelSerializer):
    source_key = serializers.CharField(source="source.key", read_only=True)
    source_name = serializers.CharField(source="source.display_name", read_only=True)

    class Meta:
        model = SourceRun
        fields = ["id", "source_key", "source_name", "status", "fetched_count", "created_count",
                  "updated_count", "ignored_count", "error_code", "error_summary", "started_at",
                  "finished_at"]
        read_only_fields = fields


class DiscoveryRunSerializer(serializers.ModelSerializer):
    source_runs = SourceRunSerializer(many=True, read_only=True)

    class Meta:
        model = DiscoveryRun
        fields = ["id", "status", "trigger_type", "started_at", "finished_at", "criteria", "summary",
                  "source_runs"]
        read_only_fields = fields


class JobSourceSerializer(serializers.ModelSerializer):
    last_run = serializers.SerializerMethodField()

    class Meta:
        model = JobSource
        fields = ["id", "key", "display_name", "source_type", "base_url", "is_enabled", "last_run"]
        read_only_fields = [f for f in fields if f != "is_enabled"]

    def get_last_run(self, source) -> dict | None:
        run = source.runs.order_by("-started_at").first()
        if run is None:
            return None
        return {"status": run.status, "finished_at": run.finished_at, "error_summary": run.error_summary}