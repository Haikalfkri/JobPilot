import logging

from celery import shared_task

from core.exceptions import InvalidWorkflow

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def refresh_matches_task(force: bool = False) -> None:
    from . import services

    try:
        counts = services.refresh_matches(force=force)
        logger.info("Match refresh finished: %s", counts)
    except InvalidWorkflow as exc:
        logger.info("Match refresh skipped: %s", exc.detail)


@shared_task(ignore_result=True)
def analyze_job_task(job_id: str, force: bool = True) -> None:
    from . import services

    try:
        services.refresh_matches(job_ids=[job_id], force=force)
    except InvalidWorkflow as exc:
        logger.info("Job analysis skipped: %s", exc.detail)