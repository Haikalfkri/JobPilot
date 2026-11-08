import logging

from celery import shared_task

from core.exceptions import Conflict, InvalidWorkflow

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def discover_jobs_task(run_id: str) -> None:
    from .discovery import run_discovery

    run_discovery(run_id)


@shared_task(ignore_result=True)
def verify_job_task(job_id: str) -> None:
    from .models import Job
    from .verification import verify_job

    job = Job.objects.filter(pk=job_id).first()
    if job is not None:
        verify_job(job)


@shared_task(ignore_result=True)
def scheduled_discovery_task() -> None:
    from .models import TriggerType
    from .services import start_discovery

    try:
        start_discovery(trigger=TriggerType.SCHEDULED)
    except (Conflict, InvalidWorkflow) as exc:
        logger.info("Scheduled discovery skipped: %s", exc.detail)