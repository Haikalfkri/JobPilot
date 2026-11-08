"""Parsing pipeline: file -> text -> suggested facts. Runs inside a Celery worker."""
import logging

from django.db import transaction

from . import storage
from .extraction import ExtractionError, extract_text
from .models import MasterResume, ParsingStatus, ResumeFact, VerificationStatus
from .parsing import parse_facts

logger = logging.getLogger(__name__)


def refresh_parsing_status(resume: MasterResume) -> None:
    """Parsed resumes are 'completed' once no parser suggestion is left to review."""
    if resume.parsing_status not in (ParsingStatus.REVIEW_REQUIRED, ParsingStatus.COMPLETED):
        return
    pending = resume.facts.filter(verification_status=VerificationStatus.PARSER_SUGGESTED).exists()
    new_status = ParsingStatus.REVIEW_REQUIRED if pending else ParsingStatus.COMPLETED
    if new_status != resume.parsing_status:
        resume.parsing_status = new_status
        resume.save(update_fields=["parsing_status"])


def _fail(resume: MasterResume, message: str) -> None:
    resume.parsing_status = ParsingStatus.FAILED
    resume.parsing_error = message
    resume.save(update_fields=["parsing_status", "parsing_error"])


def parse_resume(resume_id) -> None:
    resume = MasterResume.objects.get(pk=resume_id)
    resume.parsing_status = ParsingStatus.PROCESSING
    resume.parsing_error = ""
    resume.save(update_fields=["parsing_status", "parsing_error"])

    try:
        text = extract_text(storage.absolute_path(resume.storage_path), resume.file_type)
        if not text.strip():
            raise ExtractionError("No text could be extracted. Scanned or image-only files are not supported.")
        candidates = parse_facts(text)
    except ExtractionError as exc:
        _fail(resume, str(exc))
        return
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected parsing failure for resume %s", resume_id)  # never log resume text
        _fail(resume, "Unexpected error while parsing this file.")
        return

    with transaction.atomic():
        # Reprocessing replaces suggestions only. Confirmed and rejected facts are the user's decisions.
        resume.facts.filter(verification_status=VerificationStatus.PARSER_SUGGESTED).delete()
        kept = {(f.category, f.content.strip().lower()) for f in resume.facts.all()}
        offset = resume.facts.count()
        new_facts = []
        for candidate in candidates:
            if (candidate["category"], candidate["content"].strip().lower()) in kept:
                continue
            candidate["position"] += offset
            new_facts.append(ResumeFact(master_resume=resume, **candidate))
        ResumeFact.objects.bulk_create(new_facts)

        resume.extracted_text = text
        resume.parsing_status = ParsingStatus.REVIEW_REQUIRED
        resume.save(update_fields=["extracted_text", "parsing_status"])
        refresh_parsing_status(resume)