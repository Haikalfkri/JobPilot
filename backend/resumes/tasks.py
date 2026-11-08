from celery import shared_task

from .pipeline import parse_resume


@shared_task(ignore_result=True)  # status lives in the database
def parse_resume_task(resume_id: str) -> None:
    parse_resume(resume_id)