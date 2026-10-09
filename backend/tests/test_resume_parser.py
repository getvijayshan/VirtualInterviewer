import docx as docx_lib
import io

import pytest

from app.services.resume_parser import (
    FileTooLargeError,
    ResumeParsingError,
    UnsupportedFileTypeError,
    extract_text,
    validate_upload,
)


def test_validate_upload_accepts_pdf_and_docx():
    assert validate_upload("resume.pdf", 1000) == "pdf"
    assert validate_upload("resume.docx", 1000) == "docx"


def test_validate_upload_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload("resume.txt", 1000)


def test_validate_upload_rejects_oversized_file():
    with pytest.raises(FileTooLargeError):
        validate_upload("resume.pdf", 6 * 1024 * 1024)


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    document = docx_lib.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def test_extract_text_from_real_docx():
    data = _build_docx_bytes(["Jane Candidate", "jane@example.com", "Skills: Python, SQL"])
    text = extract_text("resume.docx", data)
    assert "Jane Candidate" in text
    assert "Python" in text


def test_extract_text_raises_on_corrupt_pdf():
    with pytest.raises(ResumeParsingError):
        extract_text("resume.pdf", b"this is not a real pdf file")


def test_extract_text_raises_on_empty_docx():
    data = _build_docx_bytes([])
    with pytest.raises(ResumeParsingError):
        extract_text("resume.docx", data)
