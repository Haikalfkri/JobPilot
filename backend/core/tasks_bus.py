"""Start a Celery task by NAME, so one app can trigger another without importing it."""
import logging

logger = logging.getLogger(__name__)


def send_task_by_name(name: str, *args, **kwargs) -> bool:
    """Best effort: a down broker must never break the caller. Returns True if the task was queued."""
    from config import celery_app

    try:
        celery_app.send_task(name, args=args, kwargs=kwargs, ignore_result=True)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Could not queue task %s", name)
        return False