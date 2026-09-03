import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import (
    Candidate,
    InterviewSession,
    Report,
    SessionStatus,
    TargetType,
    TranscriptTurn,
    TurnRole,
)
from app.services import llm


class FakeQuery:
    def __init__(self, items):
        self.items = items

    def filter_by(self, **kwargs):
        return FakeQuery([i for i in self.items if all(getattr(i, k, None) == v for k, v in kwargs.items())])

    def order_by(self, *args):
        return FakeQuery(sorted(self.items, key=lambda i: getattr(i, "turn_index", 0)))

    def all(self):
        return list(self.items)


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

    def query(self, model):
        return FakeQuery([o for o in self.added if isinstance(o, model)])


@pytest.fixture
def verified_candidate():
    return Candidate(
        id=uuid.uuid4(), name="Jane", email="jane@example.com", phone_verified_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def unverified_candidate():
    return Candidate(id=uuid.uuid4(), name="Joe", email="joe@example.com", phone_verified_at=None)


@pytest.fixture
def completed_session(verified_candidate):
    return InterviewSession(
        id=uuid.uuid4(),
        candidate_id=verified_candidate.id,
        target_type=TargetType.role,
        target_role="Backend Engineer",
        duration_min=30,
        status=SessionStatus.completed,
    )


def _turns(session_id):
    return [
        TranscriptTurn(
            id=uuid.uuid4(),
            session_id=session_id,
            turn_index=0,
            role=TurnRole.assistant,
            content="Tell me about a bug you fixed.",
            created_at=datetime.now(timezone.utc),
        ),
        TranscriptTurn(
            id=uuid.uuid4(),
            session_id=session_id,
            turn_index=1,
            role=TurnRole.user,
            content="I traced a race condition in our queue consumer.",
            created_at=datetime.now(timezone.utc),
        ),
    ]


@pytest.fixture
def fake_db(verified_candidate, completed_session):
    db = FakeDB(seed=[verified_candidate, completed_session, *_turns(completed_session.id)])
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app)


def _report_tool_response():
    tool_block = SimpleNamespace(
        type="tool_use",
        name="record_interview_report",
        input={
            "overall_score": 7.5,
            "questions": [
                {
                    "question": "Tell me about a bug you fixed.",
                    "quality": "strong",
                    "note": "Clear root cause and a concrete fix.",
                }
            ],
            "communication_notes": "Confident pacing throughout.",
        },
    )
    return SimpleNamespace(content=[tool_block])


def test_generate_report_returns_structured_scorecard(client, fake_db, monkeypatch):
    monkeypatch.setattr(llm, "create_message", lambda **kwargs: _report_tool_response())

    resp = client.post(f"/sessions/{fake_db.added[1].id}/report")

    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_score"] == 7.5
    assert body["questions"][0]["quality"] == "strong"
    assert body["communication_notes"] == "Confident pacing throughout."

    reports = [o for o in fake_db.added if isinstance(o, Report)]
    assert len(reports) == 1


def test_generate_report_is_idempotent(client, fake_db, monkeypatch):
    calls = {"count": 0}

    def _create(**kwargs):
        calls["count"] += 1
        return _report_tool_response()

    monkeypatch.setattr(llm, "create_message", _create)
    session_id = fake_db.added[1].id

    first = client.post(f"/sessions/{session_id}/report")
    second = client.post(f"/sessions/{session_id}/report")

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1  # second call returns the persisted report, no regeneration


def test_generate_report_404_for_unknown_session(client, fake_db):
    resp = client.post(f"/sessions/{uuid.uuid4()}/report")
    assert resp.status_code == 404


def test_generate_report_403_for_unverified_candidate(client, unverified_candidate, monkeypatch):
    session = InterviewSession(
        id=uuid.uuid4(),
        candidate_id=unverified_candidate.id,
        target_type=TargetType.role,
        target_role="Backend Engineer",
        duration_min=30,
        status=SessionStatus.completed,
    )
    db = FakeDB(seed=[unverified_candidate, session, *_turns(session.id)])
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = client.post(f"/sessions/{session.id}/report")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 403


def test_generate_report_409_when_session_not_completed(client, verified_candidate, monkeypatch):
    session = InterviewSession(
        id=uuid.uuid4(),
        candidate_id=verified_candidate.id,
        target_type=TargetType.role,
        target_role="Backend Engineer",
        duration_min=30,
        status=SessionStatus.in_progress,
    )
    db = FakeDB(seed=[verified_candidate, session, *_turns(session.id)])
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = client.post(f"/sessions/{session.id}/report")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 409


def test_generate_report_502_on_claude_failure(client, fake_db, monkeypatch):
    import anthropic

    def _raise(**kwargs):
        raise anthropic.APIError("boom", request=None, body=None)

    monkeypatch.setattr(llm, "create_message", _raise)
    resp = client.post(f"/sessions/{fake_db.added[1].id}/report")
    assert resp.status_code == 502


def test_get_report_404_before_generation(client, fake_db):
    resp = client.get(f"/sessions/{fake_db.added[1].id}/report")
    assert resp.status_code == 404


def test_get_report_returns_generated_report(client, fake_db, monkeypatch):
    monkeypatch.setattr(llm, "create_message", lambda **kwargs: _report_tool_response())
    session_id = fake_db.added[1].id
    client.post(f"/sessions/{session_id}/report")

    resp = client.get(f"/sessions/{session_id}/report")
    assert resp.status_code == 200
    assert resp.json()["overall_score"] == 7.5


def test_get_report_403_for_unverified_candidate(client, unverified_candidate):
    session = InterviewSession(
        id=uuid.uuid4(),
        candidate_id=unverified_candidate.id,
        target_type=TargetType.role,
        target_role="Backend Engineer",
        duration_min=30,
        status=SessionStatus.completed,
    )
    db = FakeDB(seed=[unverified_candidate, session])
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = client.get(f"/sessions/{session.id}/report")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 403
