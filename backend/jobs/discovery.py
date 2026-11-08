"""Runs a discovery: each source is invoked independently and one failing source never stops the others."""
import logging

from django.utils import timezone

from .ingestion import ingest_listing
from .models import DiscoveryRun, JobSource, RunStatus, SourceRun
from .sources import registry
from .sources.base import ListingError, SourceError

logger = logging.getLogger(__name__)


def _run_source(run: DiscoveryRun, source: JobSource) -> SourceRun:
    source_run = SourceRun.objects.create(discovery_run=run, source=source)
    invalid = 0
    try:
        adapter = registry.get_adapter(source.key)
        for raw in adapter.search(run.criteria):
            source_run.fetched_count += 1
            try:
                outcome = ingest_listing(source, adapter.parse(raw))
            except ListingError:
                invalid += 1
                source_run.ignored_count += 1
                continue
            except Exception:  # noqa: BLE001 - one bad listing must not stop the source
                logger.exception("Could not process a listing from %s", source.key)
                invalid += 1
                source_run.ignored_count += 1
                continue
            setattr(source_run, f"{outcome}_count", getattr(source_run, f"{outcome}_count") + 1)
        if invalid:
            source_run.status = RunStatus.PARTIAL
            source_run.error_code = "INVALID_LISTINGS"
            source_run.error_summary = f"{invalid} listing(s) could not be processed and were skipped."
        else:
            source_run.status = RunStatus.COMPLETED
    except SourceError as exc:
        source_run.status = RunStatus.PARTIAL if source_run.fetched_count else RunStatus.FAILED
        source_run.error_code, source_run.error_summary = exc.code, exc.message
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected failure while discovering from %s", source.key)
        source_run.status = RunStatus.PARTIAL if source_run.fetched_count else RunStatus.FAILED
        source_run.error_code = "UNEXPECTED_ERROR"
        source_run.error_summary = "Unexpected error while reading this source."
    source_run.finished_at = timezone.now()
    source_run.save()
    return source_run


def run_discovery(run_id) -> None:
    run = DiscoveryRun.objects.get(pk=run_id)
    run.status = RunStatus.RUNNING
    run.save(update_fields=["status"])

    source_runs = []
    for key in run.criteria.get("source_keys", []):
        source = JobSource.objects.filter(key=key).first()
        if source is not None:
            source_runs.append(_run_source(run, source))

    statuses = {sr.status for sr in source_runs}
    if not source_runs or statuses == {RunStatus.FAILED}:
        run.status = RunStatus.FAILED
    elif statuses == {RunStatus.COMPLETED}:
        run.status = RunStatus.COMPLETED
    else:
        run.status = RunStatus.PARTIAL
    run.summary = {
        "fetched": sum(sr.fetched_count for sr in source_runs),
        "created": sum(sr.created_count for sr in source_runs),
        "updated": sum(sr.updated_count for sr in source_runs),
        "ignored": sum(sr.ignored_count for sr in source_runs),
    }
    run.finished_at = timezone.now()
    run.save()