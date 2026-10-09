"""FL-01: extract raw text from an uploaded resume file.

Deliberately separate from LLM-based structured extraction (see app.services.llm) —
this step only turns bytes into text; it has no opinion about candidate fields.
"""

import io

import docx
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {"pdf", "docx"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # FL-01.3


class UnsupportedFileTypeError(ValueError):
    """Raised for a file extension/content-type we don't accept (FL-01.2)."""


class FileTooLargeError(ValueError):
    """Raised when the upload exceeds MAX_FILE_SIZE_BYTES (FL-01.3)."""


class ResumeParsingError(Exception):
    """Raised when a supported file type still fails to yield usable text
    (corrupt/unreadable file, FL-01.5) — callers should catch this and route
    the candidate to manual entry rather than crash."""


def _extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def validate_upload(filename: str, size_bytes: int) -> str:
    """Raises UnsupportedFileTypeError / FileTooLargeError; returns the validated extension."""
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '.{ext or '?'}' — only PDF and DOCX are accepted."
        )
    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError(
            f"File is {size_bytes / 1024 / 1024:.1f}MB — the limit is "
            f"{MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f}MB."
        )
    return ext


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _extract_docx_text(data: bytes) -> str:
    document = docx.Document(io.BytesIO(data))
    paragraphs = [p.text for p in document.paragraphs]
    return "\n".join(paragraphs).strip()


def extract_text(filename: str, data: bytes) -> str:
    """Extract raw text from a validated PDF/DOCX resume.

    Raises ResumeParsingError on a corrupt/unreadable file, or if extraction
    yields no usable text at all — both are FL-01.5 cases the caller should
    surface as a retry/manual-entry path, not a 500.
    """
    ext = _extension(filename)
    try:
        if ext == "pdf":
            text = _extract_pdf_text(data)
        elif ext == "docx":
            text = _extract_docx_text(data)
        else:
            raise UnsupportedFileTypeError(f"Unsupported file type '.{ext}'.")
    except UnsupportedFileTypeError:
        raise
    except Exception as exc:  # corrupt/unreadable file — any parser library exception
        raise ResumeParsingError(f"Could not read {ext.upper()} file: {exc}") from exc

    if not text:
        raise ResumeParsingError("No extractable text found in the file.")

    return text
