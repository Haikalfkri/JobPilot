"""Persist a normalized listing: find an existing job (deduplicate) or create a new one."""
from difflib import SequenceMatcher

from django.db import transaction
from django.utils import timezone

from .models import Job, JobSource, JobSourceListing, JobStatus, ListingStatus
from .normalization import NormalizedJob, normalize
from .sources.base import ParsedListing

MIN_DESCRIPTION_CHARS_FOR_CONTENT_MATCH = 100
SIMILARITY_THRESHOLD = 0.92
# Fields where a later source may only fill gaps, never overwrite.
_FILLABLE = ["location_text", "country_code", "salary_min", "salary_max", "salary_currency",
             "published_at", "eligible_countries"]
_UNKNOWN_FIELDS = ["work_arrangement", "remote_eligibility", "employment_type", "experience_level"]


def _same_content(job: Job, norm: NormalizedJob) -> bool:
    fields = norm.job_fields
    if len(fields["description"]) < MIN_DESCRIPTION_CHARS_FOR_CONTENT_MATCH:
        return False  # too little text to say two roles are the same
    if job.location_text and fields["location_text"] and \
            job.location_text.strip().lower() != fields["location_text"].strip().lower():
        return False
    if job.description_hash == fields["description_hash"]:
        return True
    a, b = job.description[:2000], fields["description"][:2000]
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    return matcher.quick_ratio() >= SIMILARITY_THRESHOLD and matcher.ratio() >= SIMILARITY_THRESHOLD


def find_existing(source: JobSource, norm: NormalizedJob) -> tuple[Job | None, JobSourceListing | None]:
    """1) same source + external id, 2) same canonical URL, 3) same company + title + similar text."""
    if norm.external_id:
        listing = JobSourceListing.objects.select_related("job").filter(
            source=source, external_id=norm.external_id).first()
        if listing:
            return listing.job, listing
    listing = JobSourceListing.objects.select_related("job").filter(
        source=source, canonical_url=norm.canonical_url).first()
    if listing:
        return listing.job, listing
    other = JobSourceListing.objects.select_related("job").filter(canonical_url=norm.canonical_url).first()
    if other:
        return other.job, None
    fields = norm.job_fields
    candidates = Job.objects.filter(company_name__iexact=fields["company_name"],
                                    normalized_title=fields["normalized_title"])
    for job in candidates:
        if _same_content(job, norm):
            return job, None
    return None, None


def _apply(job: Job, norm: NormalizedJob, *, overwrite: bool) -> bool:
    """Update the job from a listing. Returns True if anything changed."""
    fields, changed = norm.job_fields, False
    if overwrite:
        for name, value in fields.items():
            if getattr(job, name) != value:
                setattr(job, name, value)
                changed = True
    else:
        for name in _FILLABLE:
            if getattr(job, name) in (None, "") and fields[name] not in (None, ""):
                setattr(job, name, fields[name])
                changed = True
        for name in _UNKNOWN_FIELDS:
            if getattr(job, name) == "unknown" and fields[name] != "unknown":
                setattr(job, name, fields[name])
                changed = True
    if job.status != JobStatus.ACTIVE:  # it is listed by the source right now
        job.status = JobStatus.ACTIVE
        changed = True
    if changed:
        job.save()
    return changed


@transaction.atomic
def ingest_listing(source: JobSource, parsed: ParsedListing) -> str:
    """Returns 'created', 'updated' or 'ignored'. Raises ListingError for unusable listings."""
    norm = normalize(parsed)
    now = timezone.now()
    job, listing = find_existing(source, norm)

    if job is None:
        job = Job.objects.create(**norm.job_fields, discovered_at=now, status=JobStatus.ACTIVE)
        _create_listing(job, source, norm, now)
        return "created"

    if listing is None:  # same job seen on another source: keep both origins
        _create_listing(job, source, norm, now)
        _apply(job, norm, overwrite=False)
        return "updated"

    listing.last_seen_at = now
    listing.source_status = ListingStatus.ACTIVE
    listing.original_url = norm.original_url
    listing.canonical_url = norm.canonical_url
    listing.raw_metadata = norm.metadata
    listing.save()
    first_listing_id = job.listings.order_by("first_seen_at").values_list("id", flat=True).first()
    changed = _apply(job, norm, overwrite=(listing.id == first_listing_id))
    return "updated" if changed else "ignored"


def _create_listing(job: Job, source: JobSource, norm: NormalizedJob, now) -> JobSourceListing:
    return JobSourceListing.objects.create(
        job=job, source=source, external_id=norm.external_id, original_url=norm.original_url,
        canonical_url=norm.canonical_url, raw_metadata=norm.metadata,
        first_seen_at=now, last_seen_at=now, source_status=ListingStatus.ACTIVE,
    )