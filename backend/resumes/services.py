"""Business rules for resumes. Views call these; they contain no HTTP logic."""
import logging

from django.db import transaction
from django.db.models import Max

from core.exceptions import InvalidWorkflow

from . import storage
from .models import MasterResume, ParsingStatus, ResumeFact, VerificationStatus
from .pipeline import refresh_parsing_status
from .tasks import parse_resume_task

logger = logging.getLogger(__name__)


def _enqueue_parsing(resume: MasterResume) -> None:
    try:
        parse_resume_task.delay(str(resume.id))
    except Exception:  # noqa: BLE001 - broker down; the user can retry with "reprocess"
        logger.exception("Could not queue parsing for resume %s", resume.id)
        resume.parsing_status = ParsingStatus.FAILED
        resume.parsing_error = "The background worker is unavailable. Try reprocessing in a moment."
        resume.save(update_fields=["parsing_status", "parsing_error"])


def create_master_resume(uploaded_file) -> tuple[MasterResume, int | None]:
    """Validate, store and queue a new resume version. Returns (resume, duplicate_of_version)."""
    upload = storage.validate_upload(uploaded_file)
    duplicate = MasterResume.objects.filter(sha256=upload.sha256).order_by("version_number").first()
    relative_path = storage.save_original(upload)

    with transaction.atomic():
        latest = MasterResume.objects.aggregate(latest=Max("version_number"))["latest"] or 0
        resume = MasterResume.objects.create(
            version_number=latest + 1,
            original_filename=upload.original_filename,
            storage_path=relative_path,
            file_type=upload.file_type,
            sha256=upload.sha256,
        )
    _enqueue_parsing(resume)
    resume.refresh_from_db()
    return resume, duplicate.version_number if duplicate else None


def reprocess_resume(resume: MasterResume) -> MasterResume:
    if resume.parsing_status in (ParsingStatus.PENDING, ParsingStatus.PROCESSING):
        raise InvalidWorkflow("This resume is already being processed.")
    resume.parsing_status = ParsingStatus.PENDING
    resume.parsing_error = ""
    resume.save(update_fields=["parsing_status", "parsing_error"])
    _enqueue_parsing(resume)
    resume.refresh_from_db()
    return resume


@transaction.atomic
def activate_resume(resume: MasterResume) -> MasterResume:
    if resume.parsing_status not in (ParsingStatus.REVIEW_REQUIRED, ParsingStatus.COMPLETED):
        raise InvalidWorkflow("Only a successfully parsed resume can be activated.")
    MasterResume.objects.filter(is_active=True).exclude(pk=resume.pk).update(is_active=False)
    resume.is_active = True
    resume.save(update_fields=["is_active"])
    return resume


@transaction.atomic
def update_fact(fact: ResumeFact, data: dict) -> ResumeFact:
    content_changed = "content" in data and data["content"] != fact.content
    for field in ("content", "structured_value"):
        if field in data:
            setattr(fact, field, data[field])
    if "verification_status" in data:
        fact.verification_status = data["verification_status"]
    elif content_changed:
        fact.verification_status = VerificationStatus.USER_CONFIRMED  # a user edit is a confirmation
    fact.save()
    refresh_parsing_status(fact.master_resume)
    return fact


@transaction.atomic
def create_fact(resume: MasterResume, data: dict) -> ResumeFact:
    last = resume.facts.aggregate(last=Max("position"))["last"]
    fact = ResumeFact.objects.create(
        master_resume=resume,
        category=data["category"],
        fact_key=data.get("fact_key") or None,
        content=data["content"],
        structured_value=data.get("structured_value"),
        source_location="added by user",
        verification_status=VerificationStatus.USER_CONFIRMED,
        position=0 if last is None else last + 1,
    )
    refresh_parsing_status(resume)
    return fact