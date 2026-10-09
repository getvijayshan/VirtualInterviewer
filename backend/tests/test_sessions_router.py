import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Candidate


class FakeDB:
    def __init__(self, seed=None):
        self.added = list(seed or [])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def get(self, model, id_):
        for obj in self.added:
            if isinstance(obj, model) and getattr(obj, "id", None) == id_:
                return obj
        return None


@pytest.fixture
def candidate():
    return Candidate(id=uuid.uuid4(), name="Jane", email="jane@example.com")


@pytest.fixture
def fake_db(candidate):
    db = FakeDB(seed=[candidate])
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_target_options_lists_roles_and_topics(client, fake_db):
    resp = client.get("/sessions/target-options")
    assert resp.status_code == 200
    body = resp.json()
    assert "Backend Engineer" in body["roles"]
    assert any(t["value"] == "data_structures" for t in body["topics"])


def test_create_session_with_jd(client, fake_db, candidate):
    resp = client.post(
        "/sessions",
        json={
            "candidate_id": str(candidate.id),
            "target_type": "jd",
            "jd_text": "Backend Engineer role description...",
            "consent": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_type"] == "jd"
    assert body["duration_min"] == 30
    assert body["status"] == "pending"
    assert body["consent_at"] is not None


def test_create_session_with_role(client, fake_db, candidate):
    resp = client.post(
        "/sessions",
        json={
            "candidate_id": str(candidate.id),
            "target_type": "role",
            "target_role": "Backend Engineer",
            "consent": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["target_role"] == "Backend Engineer"


def test_create_session_with_topic(client, fake_db, candidate):
    resp = client.post(
        "/sessions",
        json={
            "candidate_id": str(candidate.id),
            "target_type": "topic",
            "target_topic": "system_design",
            "consent": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["target_topic"] == "system_design"


def test_create_session_rejects_unknown_role(client, fake_db, candidate):
    resp = client.post(
        "/sessions",
        json={
            "candidate_id": str(candidate.id),
            "target_type": "role",
            "target_role": "Astronaut",
            "consent": True,
        },
    )
    assert resp.status_code == 422


def test_create_session_rejects_missing_jd_text(client, fake_db, candidate):
    resp = client.post(
        "/sessions",
        json={"candidate_id": str(candidate.id), "target_type": "jd", "consent": True},
    )
    assert resp.status_code == 422


def test_create_session_rejects_declined_consent(client, fake_db, candidate):
    resp = client.post(
        "/sessions",
        json={
            "candidate_id": str(candidate.id),
            "target_type": "role",
            "target_role": "Backend Engineer",
            "consent": False,
        },
    )
    assert resp.status_code == 422
    assert len(fake_db.added) == 1  # only the seeded candidate — no session created


def test_create_session_404_for_unknown_candidate(client, fake_db):
    resp = client.post(
        "/sessions",
        json={
            "candidate_id": str(uuid.uuid4()),
            "target_type": "role",
            "target_role": "Backend Engineer",
            "consent": True,
        },
    )
    assert resp.status_code == 404


def test_get_session_404_for_unknown_id(client, fake_db):
    resp = client.get(f"/sessions/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_session_returns_created_session(client, fake_db, candidate):
    create_resp = client.post(
        "/sessions",
        json={
            "candidate_id": str(candidate.id),
            "target_type": "topic",
            "target_topic": "algorithms",
            "consent": True,
        },
    )
    session_id = create_resp.json()["id"]

    resp = client.get(f"/sessions/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["target_topic"] == "algorithms"
