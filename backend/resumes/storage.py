"""Upload validation and local file storage. Files never get a public URL."""
import hashlib
import io
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from rest_framework.exceptions import ValidationError

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx"}
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024  # guard against zip bombs


@dataclass
class ValidatedUpload:
    file_type: str
    content: bytes
    sha256: str
    original_filename: str


def _reject(message: str):
    raise ValidationError({"file": [message]})


def validate_upload(uploaded_file) -> ValidatedUpload:
    name = PurePath(uploaded_file.name or "").name  # drop any client-supplied directories
    file_type = ALLOWED_EXTENSIONS.get(PurePath(name).suffix.lower())
    if not file_type:
        _reject("Only PDF and DOCX files are supported.")
    if uploaded_file.size == 0:
        _reject("The file is empty.")
    if uploaded_file.size > settings.MAX_RESUME_UPLOAD_BYTES:
        limit_mb = settings.MAX_RESUME_UPLOAD_BYTES // (1024 * 1024)
        _reject(f"The file is larger than the {limit_mb} MB limit.")

    content = uploaded_file.read()
    if file_type == "pdf" and not content.startswith(b"%PDF-"):
        _reject("This file is not a valid PDF.")
    if file_type == "docx" and not _looks_like_docx(content):
        _reject("This file is not a valid DOCX document.")

    return ValidatedUpload(
        file_type=file_type,
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        original_filename=name[:255],
    )


def _looks_like_docx(content: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            return info.file_size <= MAX_DOCX_XML_BYTES
    except (zipfile.BadZipFile, KeyError):
        return False


def _storage() -> FileSystemStorage:
    return FileSystemStorage(location=settings.MEDIA_ROOT)


def save_original(upload: ValidatedUpload) -> str:
    """Save under a generated UUID name (never trust the uploaded name). Returns the relative path."""
    relative = f"resumes/original/{uuid.uuid4()}.{upload.file_type}"
    return _storage().save(relative, ContentFile(upload.content))


def absolute_path(relative_path: str) -> str:
    return _storage().path(relative_path)