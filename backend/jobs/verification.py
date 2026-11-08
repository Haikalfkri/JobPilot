"""Availability verification.

Only stored listing URLs on a source's own hosts are requested (never a URL supplied by a client).
A 200 means "the page exists", a 404/410 means "gone". Anything else is inconclusive and becomes
'unknown', never 'closed' (docs/features-and-requirements.md, FR-JOB-04).
"""
from urllib.parse import urlsplit

import httpx
from django.conf import settings
from django.utils import timezone

from .models import Job, JobStatus, ListingStatus
from .sources.base import USER_AGENT
from .sources.registry import REGISTRY


def _check(listing, client: httpx.Client) -> str:
    adapter_cls = REGISTRY.get(listing.source.key)
    host = (urlsplit(listing.original_url).hostname or "").lower()
    if adapter_cls is None or host not in adapter_cls.allowed_hosts:
        return ListingStatus.UNKNOWN  # never fetch hosts we do not know
    try:
        response = client.get(listing.original_url)
    except httpx.HTTPError:
        return ListingStatus.UNKNOWN
    if response.status_code == 200:
        return ListingStatus.ACTIVE
    if response.status_code in (404, 410):
        return ListingStatus.CLOSED
    return ListingStatus.UNKNOWN


def verify_job(job: Job, client: httpx.Client | None = None) -> str:
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=settings.DISCOVERY_REQUEST_TIMEOUT_SECONDS,
                              headers={"User-Agent": USER_AGENT}, follow_redirects=False)
    try:
        now = timezone.now()
        results = []
        for listing in job.listings.select_related("source"):
            listing.source_status = _check(listing, client)
            listing.last_checked_at = now
            listing.save(update_fields=["source_status", "last_checked_at"])
            results.append(listing.source_status)
    finally:
        if owns_client:
            client.close()

    if ListingStatus.ACTIVE in results:
        job.status, job.last_verified_at = JobStatus.ACTIVE, now
    elif results and all(r == ListingStatus.CLOSED for r in results):
        job.status, job.last_verified_at = JobStatus.CLOSED, now
    else:
        job.status = JobStatus.UNKNOWN
    job.save(update_fields=["status", "last_verified_at", "updated_at"])
    return job.status