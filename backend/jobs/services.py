"""Business rules for discovery and sources. Views call these; they contain no HTTP logic."""
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.exceptions import Conflict, InvalidWorkflow, ServiceUnavailable

from .models import DiscoveryRun, JobSource, RunStatus, TriggerType
from .sources.registry import REGISTRY
from .tasks import discover_jobs_task

logger = logging.getLogger(__name__)

STALE_RUN_AFTER = timedelta(minutes=30)  # a run older than this is assumed dead (crashed worker)
MAX_KEYWORDS = 10


def sync_sources() -> None:
    """Make sure every registered adapter has a JobSource row. The registry is the source of truth."""
    for key, adapter in REGISTRY.items():
        JobSource.objects.get_or_create(key=key, defaults={
            "display_name": adapter.display_name,
            "source_type": adapter.source_type,
            "base_url": adapter.base_url,
        })


def has_active_run() -> bool:
    cutoff = timezone.now() - STALE_RUN_AFTER
    return DiscoveryRun.objects.filter(
        status__in=[RunStatus.PENDING, RunStatus.RUNNING], started_at__gte=cutoff).exists()


def _clean_keywords(keywords) -> list[str]:
    if keywords is None:
        return list(settings.DISCOVERY_DEFAULT_KEYWORDS)
    cleaned, seen = [], set()
    for keyword in keywords:
        keyword = " ".join(str(keyword).split())
        if keyword and keyword.lower() not in seen:
            seen.add(keyword.lower())
            cleaned.append(keyword[:50])
    return cleaned[:MAX_KEYWORDS]


def start_discovery(*, source_keys=None, keywords=None, trigger=TriggerType.MANUAL) -> DiscoveryRun:
    sync_sources()
    enabled = set(JobSource.objects.filter(is_enabled=True).values_list("key", flat=True))
    if source_keys is None:
        chosen = sorted(enabled)
    else:
        bad = [k for k in source_keys if k not in REGISTRY or k not in enabled]
        if bad:
            raise ValidationError({"source_keys": [f"Unknown or disabled source: {', '.join(bad)}."]})
        chosen = list(dict.fromkeys(source_keys))
    if not chosen:
        raise InvalidWorkflow("There are no enabled job sources.")
    if has_active_run():
        raise Conflict("A discovery run is already in progress.")

    run = DiscoveryRun.objects.create(
        trigger_type=trigger,
        criteria={"source_keys": chosen, "keywords": _clean_keywords(keywords)},
    )
    try:
        discover_jobs_task.delay(str(run.id))
    except Exception:  # noqa: BLE001 - broker down
        logger.exception("Could not queue discovery run %s", run.id)
        run.status = RunStatus.FAILED
        run.finished_at = timezone.now()
        run.summary = {"error": "The background worker is unavailable."}
        run.save()
        raise ServiceUnavailable() from None
    run.refresh_from_db()
    return run