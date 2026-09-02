import io
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Candidate, InterviewSession, SessionStatus, TargetType, TranscriptTurn, TurnRole
from app.routers import interview as interview_router
from app.services import llm, storage


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
        self.rollback_calls = 0

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def rollback(self):
        self.rollback_calls += 1

    def get(self, model, id_):
        for obj in self.added:
            if isinstance(obj, model) and getattr(obj, "id", None) == id_:
                return obj
        return None

    def query(self, model):
        return FakeQuery([o for o in self.added if isinstance(o, model)])


@pytest.fixture
def candidate():
    return Candidate(id=uuid.uuid4(), name="Jane", email="jane@example.com", resume_parsed_json={"skills": ["Python"]})


@pytest.fixture
def pending_session(candidate):
    return InterviewSession(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        target_type=TargetType.role,
        target_role="Backend Engineer",
        duration_min=30,
        status=SessionStatus.pending,
    )


@pytest.fixture
def fake_db(candidate, pending_session):
    db = FakeDB(seed=[candidate, pending_session])
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app)


def _text_response(text: str):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def test_start_interview_creates_first_turn(client, fake_db, pending_session, monkeypatch):
    monkeypatch.setattr(llm, "create_message", lambda **kwargs: _text_response("Tell me about a recent project."))

    resp = client.post(f"/sessions/{pending_session.id}/start")

    assert resp.status_code == 200
    body = resp.json()
    assert body["question"] == "Tell me about a recent project."
    assert body["turn_index"] == 0
    assert body["session_status"] == "in_progress"
    assert body["ended"] is False
    assert pending_session.status == SessionStatus.in_progress
    assert pending_session.started_at is not None
    turns = [o for o in fake_db.added if isinstance(o, TranscriptTurn)]
    assert len(turns) == 1
    assert turns[0].role == TurnRole.assistant


def test_start_interview_rejects_when_already_started(client, fake_db, pending_session):
    pending_session.status = SessionStatus.in_progress
    resp = client.post(f"/sessions/{pending_session.id}/start")
    assert resp.status_code == 409


def test_start_interview_404_for_unknown_session(client, fake_db):
    resp = client.post(f"/sessions/{uuid.uuid4()}/start")
    assert resp.status_code == 404


def _start_session(db: FakeDB, session: InterviewSession, opening_question="Opening question?"):
    session.status = SessionStatus.in_progress
    session.started_at = datetime.now(timezone.utc)
    db.add(
        TranscriptTurn(
            id=uuid.uuid4(),
            session_id=session.id,
            turn_index=0,
            role=TurnRole.assistant,
            content=opening_question,
            created_at=datetime.now(timezone.utc),
        )
    )


def test_submit_answer_returns_next_question(client, fake_db, pending_session, monkeypatch):
    _start_session(fake_db, pending_session)
    monkeypatch.setattr(storage, "upload_interview_answer_audio", lambda **kwargs: "https://fake-s3/answer.webm")
    monkeypatch.setattr(interview_router, "transcribe", lambda audio: "My answer to the question.")
    monkeypatch.setattr(llm, "create_message", lambda **kwargs: _text_response("Follow-up question?"))

    resp = client.post(
        f"/sessions/{pending_session.id}/turns",
        files={"audio": ("answer.webm", io.BytesIO(b"fake-audio"), "audio/webm")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["question"] == "Follow-up question?"
    assert body["turn_index"] == 2
    assert body["ended"] is False
    assert body["answer_text"] == "My answer to the question."

    turns = sorted(
        [o for o in fake_db.added if isinstance(o, TranscriptTurn)], key=lambda t: t.turn_index
    )
    assert len(turns) == 3  # opening question + user answer + follow-up question
    assert turns[1].role == TurnRole.user
    assert turns[1].content == "My answer to the question."
    assert turns[1].audio_file_url == "https://fake-s3/answer.webm"
    assert turns[2].role == TurnRole.assistant


def test_submit_answer_ends_session_when_time_up(client, fake_db, pending_session, monkeypatch):
    _start_session(fake_db, pending_session)
    pending_session.started_at = datetime.now(timezone.utc) - timedelta(minutes=45)  # 30 min duration, well past

    monkeypatch.setattr(storage, "upload_interview_answer_audio", lambda **kwargs: "https://fake-s3/answer.webm")
    monkeypatch.setattr(interview_router, "transcribe", lambda audio: "My final answer.")

    called = {"create_message": False}

    def _should_not_be_called(**kwargs):
        called["create_message"] = True
        return _text_response("should not happen")

    monkeypatch.setattr(llm, "create_message", _should_not_be_called)

    resp = client.post(
        f"/sessions/{pending_session.id}/turns",
        files={"audio": ("answer.webm", io.BytesIO(b"fake-audio"), "audio/webm")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ended"] is True
    assert body["question"] is None
    assert body["session_status"] == "completed"
    assert body["answer_text"] == "My final answer."
    assert called["create_message"] is False  # hard stop checked before any further Claude call
    assert pending_session.status == SessionStatus.completed
    assert pending_session.ended_at is not None

    user_turns = [o for o in fake_db.added if isinstance(o, TranscriptTurn) and o.role == TurnRole.user]
    assert len(user_turns) == 1  # the candidate's last answer is still saved


def test_submit_answer_422_on_transcription_failure(client, fake_db, pending_session, monkeypatch):
    _start_session(fake_db, pending_session)
    from app.services.transcription import TranscriptionError

    def _raise(audio):
        raise TranscriptionError("bad audio")

    monkeypatch.setattr(interview_router, "transcribe", _raise)

    resp = client.post(
        f"/sessions/{pending_session.id}/turns",
        files={"audio": ("answer.webm", io.BytesIO(b"fake-audio"), "audio/webm")},
    )
    assert resp.status_code == 422
    user_turns = [o for o in fake_db.added if isinstance(o, TranscriptTurn) and o.role == TurnRole.user]
    assert len(user_turns) == 0


def test_submit_answer_rejects_when_not_started(client, fake_db, pending_session):
    resp = client.post(
        f"/sessions/{pending_session.id}/turns",
        files={"audio": ("answer.webm", io.BytesIO(b"fake-audio"), "audio/webm")},
    )
    assert resp.status_code == 409


def test_submit_answer_rejects_when_already_completed(client, fake_db, pending_session):
    pending_session.status = SessionStatus.completed
    resp = client.post(
        f"/sessions/{pending_session.id}/turns",
        files={"audio": ("answer.webm", io.BytesIO(b"fake-audio"), "audio/webm")},
    )
    assert resp.status_code == 409


def test_submit_answer_502_on_claude_failure_rolls_back(client, fake_db, pending_session, monkeypatch):
    _start_session(fake_db, pending_session)
    monkeypatch.setattr(storage, "upload_interview_answer_audio", lambda **kwargs: "https://fake-s3/answer.webm")
    monkeypatch.setattr(interview_router, "transcribe", lambda audio: "My answer.")

    import anthropic

    def _raise(**kwargs):
        raise anthropic.APIError("boom", request=None, body=None)

    monkeypatch.setattr(llm, "create_message", _raise)

    resp = client.post(
        f"/sessions/{pending_session.id}/turns",
        files={"audio": ("answer.webm", io.BytesIO(b"fake-audio"), "audio/webm")},
    )
    assert resp.status_code == 502
    assert fake_db.rollback_calls == 1


def test_get_transcript_returns_ordered_turns(client, fake_db, pending_session):
    _start_session(fake_db, pending_session)
    resp = client.get(f"/sessions/{pending_session.id}/transcript")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert len(body["turns"]) == 1
    assert body["turns"][0]["role"] == "assistant"
    assert body["time_remaining_seconds"] > 0


def test_get_transcript_404_for_unknown_session(client, fake_db):
    resp = client.get(f"/sessions/{uuid.uuid4()}/transcript")
    assert resp.status_code == 404


def test_end_session_marks_completed(client, fake_db, pending_session):
    _start_session(fake_db, pending_session)
    resp = client.post(f"/sessions/{pending_session.id}/end")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ended"] is True
    assert body["session_status"] == "completed"
    assert pending_session.ended_at is not None


def test_end_session_is_idempotent(client, fake_db, pending_session):
    _start_session(fake_db, pending_session)
    client.post(f"/sessions/{pending_session.id}/end")
    first_ended_at = pending_session.ended_at

    resp = client.post(f"/sessions/{pending_session.id}/end")
    assert resp.status_code == 200
    assert pending_session.ended_at == first_ended_at
