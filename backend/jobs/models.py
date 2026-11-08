import uuid

from django.db import models
from django.db.models import Q


class SourceType(models.TextChoices):
    API = "api"
    FEED = "feed"
    PUBLIC_PAGE = "public_page"
    COMPANY_CAREER_PAGE = "company_career_page"
    MANUAL = "manual"


class WorkArrangement(models.TextChoices):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class RemoteEligibility(models.TextChoices):
    WORLDWIDE = "worldwide"
    APAC = "apac"
    COUNTRY_SPECIFIC = "country_specific"
    REGION_SPECIFIC = "region_specific"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class EmploymentType(models.TextChoices):
    FULL_TIME = "full_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    PART_TIME = "part_time"
    UNKNOWN = "unknown"


class ExperienceLevel(models.TextChoices):
    GRADUATE = "graduate"
    JUNIOR = "junior"
    ASSOCIATE = "associate"
    MID = "mid"
    SENIOR = "senior"
    UNKNOWN = "unknown"


class JobStatus(models.TextChoices):
    ACTIVE = "active"
    EXPIRED = "expired"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class ListingStatus(models.TextChoices):
    ACTIVE = "active"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class RunStatus(models.TextChoices):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"  # only meaningful for SourceRun


class TriggerType(models.TextChoices):
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class JobSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    base_url = models.URLField(blank=True, null=True)
    is_enabled = models.BooleanField(default=True)
    # Never put credentials here (see docs/database-design.md).
    configuration = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self) -> str:
        return self.display_name


class Job(models.Model):
    """The normalized identity of a job. The same job may have several source listings."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    normalized_title = models.CharField(max_length=300)
    company_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")  # plain text, never HTML
    location_text = models.CharField(max_length=300, null=True, blank=True)
    country_code = models.CharField(max_length=2, null=True, blank=True)
    work_arrangement = models.CharField(
        max_length=10, choices=WorkArrangement.choices, default=WorkArrangement.UNKNOWN
    )
    remote_eligibility = models.CharField(
        max_length=20, choices=RemoteEligibility.choices, default=RemoteEligibility.UNKNOWN
    )
    # ISO country codes for country_specific; upper-case region tokens (e.g. "EUROPE") for region_specific.
    eligible_countries = models.JSONField(null=True, blank=True)
    employment_type = models.CharField(
        max_length=12, choices=EmploymentType.choices, default=EmploymentType.UNKNOWN
    )
    experience_level = models.CharField(
        max_length=12, choices=ExperienceLevel.choices, default=ExperienceLevel.UNKNOWN
    )
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=3, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    discovered_at = models.DateTimeField()
    last_verified_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=JobStatus.choices, default=JobStatus.UNKNOWN)
    description_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-discovered_at"]
        indexes = [
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["normalized_title"]),
            models.Index(fields=["country_code", "work_arrangement"]),
            models.Index(fields=["description_hash"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} @ {self.company_name}"


class JobSourceListing(models.Model):
    """Preserves each source's own listing so a job keeps every origin and original URL."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="listings")
    source = models.ForeignKey(JobSource, on_delete=models.CASCADE, related_name="listings")
    external_id = models.CharField(max_length=200, null=True, blank=True)
    original_url = models.URLField(max_length=1000)
    canonical_url = models.URLField(max_length=1000, null=True, blank=True)
    raw_metadata = models.JSONField(null=True, blank=True)
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    last_checked_at = models.DateTimeField(null=True, blank=True)
    source_status = models.CharField(
        max_length=10, choices=ListingStatus.choices, default=ListingStatus.UNKNOWN
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=Q(external_id__isnull=False),
                name="unique_source_external_id",
            )
        ]
        indexes = [
            models.Index(fields=["canonical_url"]),
            models.Index(fields=["job", "source"]),
        ]


class DiscoveryRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=RunStatus.choices, default=RunStatus.PENDING)
    trigger_type = models.CharField(max_length=10, choices=TriggerType.choices)
    criteria = models.JSONField(default=dict)  # source_keys and keywords used for this run
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]


class SourceRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    discovery_run = models.ForeignKey(DiscoveryRun, on_delete=models.CASCADE, related_name="source_runs")
    source = models.ForeignKey(JobSource, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=10, choices=RunStatus.choices, default=RunStatus.RUNNING)
    fetched_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    ignored_count = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=50, null=True, blank=True)
    error_summary = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["started_at"]