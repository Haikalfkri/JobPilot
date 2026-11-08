import uuid

from django.db import models
from django.db.models import Q


class ParsingStatus(models.TextChoices):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class FileType(models.TextChoices):
    PDF = "pdf"
    DOCX = "docx"


class FactCategory(models.TextChoices):
    PERSONAL = "personal"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILL = "skill"
    PROJECT = "project"
    CERTIFICATION = "certification"
    LANGUAGE = "language"
    LINK = "link"


class VerificationStatus(models.TextChoices):
    PARSER_SUGGESTED = "parser_suggested"
    USER_CONFIRMED = "user_confirmed"
    REJECTED = "rejected"


class MasterResume(models.Model):
    """One uploaded resume version. Files are stored by relative path under MEDIA_ROOT."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version_number = models.PositiveIntegerField(unique=True)
    original_filename = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=4, choices=FileType.choices)
    sha256 = models.CharField(max_length=64, db_index=True)
    extracted_text = models.TextField(blank=True, default="")
    parsing_status = models.CharField(
        max_length=20, choices=ParsingStatus.choices, default=ParsingStatus.PENDING
    )
    parsing_error = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            # At most one row may have is_active = true.
            models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="one_active_master_resume",
            )
        ]

    def __str__(self) -> str:
        return f"Resume v{self.version_number} ({self.original_filename})"


class ResumeFact(models.Model):
    """A traceable candidate fact. A parser suggestion is NOT a verified fact."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    master_resume = models.ForeignKey(MasterResume, on_delete=models.CASCADE, related_name="facts")
    category = models.CharField(max_length=20, choices=FactCategory.choices)
    fact_key = models.CharField(max_length=50, null=True, blank=True)
    content = models.TextField()
    structured_value = models.JSONField(null=True, blank=True)
    source_location = models.CharField(max_length=100, blank=True, default="")
    verification_status = models.CharField(
        max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.PARSER_SUGGESTED
    )
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at"]
        indexes = [models.Index(fields=["master_resume", "category"])]

    def __str__(self) -> str:
        return f"{self.category}: {self.content[:40]}"