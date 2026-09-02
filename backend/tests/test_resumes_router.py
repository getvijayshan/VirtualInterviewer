import io
import uuid

import docx as docx_lib
import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services import llm, storage


class FakeDB:
    """Minimal stand-in for a SQLAlchemy Session — no real database involved."""

    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def get(self, model, id_):
        for obj in self.added:
            if getattr(obj, "id", None) == id_:
                return obj
        return None


@pytest.fixture
def fake_db():
    db = FakeDB()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app)


def _docx_bytes(text: str) -> bytes:
    document = docx_lib.Document()
    document.add_paragraph(text)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def test_upload_rejects_unsupported_file_type(client, fake_db):
    resp = client.post(
        "/resumes",
        files={"file": ("resume.txt", b"not a resume", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_rejects_oversized_file(client, fake_db):
    big = b"x" * (6 * 1024 * 1024)
    resp = client.post(
        "/resumes",
        files={"file": ("resume.pdf", big, "application/pdf")},
    )
    assert resp.status_code == 413


def test_upload_success_persists_candidate_and_returns_parsed_fields(client, fake_db, monkeypatch):
    monkeypatch.setattr(storage, "upload_resume_file", lambda **kwargs: "https://fake-s3/resume.docx")
    monkeypatch.setattr(
        llm,
        "extract_candidate_fields",
        lambda text: {
            "name": "Jane Candidate",
            "email": "jane@example.com",
            "phone": "",
            "skills": ["Python"],
            "experience": [],
            "education": [],
            "projects": [],
        },
    )

    data = _docx_bytes("Jane Candidate — jane@example.com — Python")
    resp = client.post(
        "/resumes",
        files={
            "file": (
                "resume.docx",
                data,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_manual_entry"] is False
    assert body["parsed"]["name"] == "Jane Candidate"
    assert body["resume_file_url"] == "https://fake-s3/resume.docx"
    assert uuid.UUID(body["candidate_id"])  # valid UUID
    assert len(fake_db.added) == 1
    assert fake_db.added[0].email == "jane@example.com"


def test_get_resume_returns_404_for_unknown_id(client, fake_db):
    resp = client.get(f"/resumes/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_resume_returns_persisted_candidate(client, fake_db, monkeypatch):
    monkeypatch.setattr(storage, "upload_resume_file", lambda **kwargs: "https://fake-s3/resume.docx")
    monkeypatch.setattr(
        llm,
        "extract_candidate_fields",
        lambda text: {"name": "Jane Candidate", "email": "jane@example.com", "skills": [], "experience": [], "education": [], "projects": []},
    )
    data = _docx_bytes("Jane Candidate")
    upload_resp = client.post(
        "/resumes",
        files={
            "file": (
                "resume.docx",
                data,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    candidate_id = upload_resp.json()["candidate_id"]

    resp = client.get(f"/resumes/{candidate_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Jane Candidate"


def test_upload_corrupt_file_routes_to_manual_entry_instead_of_crashing(client, fake_db, monkeypatch):
    monkeypatch.setattr(storage, "upload_resume_file", lambda **kwargs: "https://fake-s3/resume.pdf")

    resp = client.post(
        "/resumes",
        files={"file": ("resume.pdf", b"not actually a pdf", "application/pdf")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_manual_entry"] is True
    assert body["parsed"] is None
    assert body["error"]
    # the candidate record (with the raw file URL) is still persisted — FL-01.6/.5
    assert len(fake_db.added) == 1
