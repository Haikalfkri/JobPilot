"""Raw text extraction from PDF and DOCX files. No interpretation happens here."""
import pymupdf
from django.conf import settings
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


class ExtractionError(Exception):
    """The file could not be turned into text. The message is safe to show to the user."""


def extract_text(path: str, file_type: str) -> str:
    if file_type == "pdf":
        return _extract_pdf(path)
    if file_type == "docx":
        return _extract_docx(path)
    raise ExtractionError("Unsupported file type.")


def _extract_pdf(path: str) -> str:
    try:
        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                raise ExtractionError("The PDF is password-protected.")
            if doc.page_count > settings.RESUME_MAX_PAGES:
                raise ExtractionError(f"The PDF has more than {settings.RESUME_MAX_PAGES} pages.")
            return "\n".join(page.get_text() for page in doc)
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("The PDF could not be read.") from exc


def _extract_docx(path: str) -> str:
    try:
        document = Document(path)
        lines: list[str] = []
        # iter_inner_content keeps paragraphs and tables in document order.
        for block in document.iter_inner_content():
            if isinstance(block, Paragraph):
                lines.append(block.text)
            elif isinstance(block, Table):
                for row in block.rows:
                    cells: list[str] = []
                    for cell in row.cells:
                        text = cell.text.strip()
                        if text and (not cells or cells[-1] != text):  # merged cells repeat
                            cells.append(text)
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        raise ExtractionError("The DOCX file could not be read.") from exc