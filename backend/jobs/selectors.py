"""Read-side queries for jobs."""
from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from .models import Job

_ORDERINGS = {
    "published_at": [F("published_at").asc(nulls_last=True), "discovered_at"],
    "-published_at": [F("published_at").desc(nulls_last=True), "-discovered_at"],
    "discovered_at": ["discovered_at"],
    "-discovered_at": ["-discovered_at"],
}


def filter_jobs(params: dict):
    queryset = Job.objects.prefetch_related("listings__source")
    if "q" in params:
        queryset = queryset.filter(Q(title__icontains=params["q"]) | Q(company_name__icontains=params["q"]))
    if "country_code" in params:
        queryset = queryset.filter(country_code=params["country_code"].upper())
    for field in ("work_arrangement", "remote_eligibility", "employment_type", "experience_level", "status"):
        if field in params:
            queryset = queryset.filter(**{field: params[field]})
    if "source" in params:
        queryset = queryset.filter(listings__source__key=params["source"]).distinct()
    if "published_within_days" in params:
        cutoff = timezone.now() - timedelta(days=params["published_within_days"])
        queryset = queryset.filter(published_at__gte=cutoff)
    return queryset.order_by(*_ORDERINGS[params.get("ordering", "-published_at")])