import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Candidate, OtpCode
from app.services import otp


class FakeQuery:
    def __init__(self, items):
        self.items = items

    def filter_by(self, **kwargs):
        return FakeQuery([i for i in self.items if all(getattr(i, k, None) == v for k, v in kwargs.items())])

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


@pytest.fixture(autouse=True)
def capture_sent_otp(monkeypatch):
    sent = {}

    def _fake_send(phone, code):
        sent["phone"] = phone
        sent["code"] = code

    monkeypatch.setattr(otp, "send_otp", _fake_send)
    return sent


def test_request_otp_persists_record_and_sends_it(client, fake_db, candidate, capture_sent_otp, monkeypatch):
    monkeypatch.setattr(otp, "generate_code", lambda: "123456")

    resp = client.post("/auth/otp/request", json={"candidate_id": str(candidate.id), "phone": "+15551234567"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["expires_in_seconds"] == otp.OTP_TTL_MINUTES * 60
    assert capture_sent_otp["phone"] == "+15551234567"
    assert capture_sent_otp["code"] == "123456"
    assert candidate.phone == "+15551234567"

    records = [o for o in fake_db.added if isinstance(o, OtpCode)]
    assert len(records) == 1
    assert records[0].code_hash == otp.hash_code("123456")


def test_request_otp_returns_debug_code_in_development(client, fake_db, candidate, monkeypatch):
    monkeypatch.setattr(otp, "generate_code", lambda: "654321")
    from app.routers import auth as auth_router

    monkeypatch.setattr(auth_router.settings, "app_env", "development")

    resp = client.post("/auth/otp/request", json={"candidate_id": str(candidate.id), "phone": "+15551234567"})
    assert resp.json()["debug_code"] == "654321"


def test_request_otp_omits_debug_code_outside_development(client, fake_db, candidate, monkeypatch):
    from app.routers import auth as auth_router

    monkeypatch.setattr(auth_router.settings, "app_env", "production")

    resp = client.post("/auth/otp/request", json={"candidate_id": str(candidate.id), "phone": "+15551234567"})
    assert resp.json()["debug_code"] is None


def test_request_otp_404_for_unknown_candidate(client, fake_db):
    resp = client.post("/auth/otp/request", json={"candidate_id": str(uuid.uuid4()), "phone": "+15551234567"})
    assert resp.status_code == 404


def test_request_otp_rejects_blank_phone(client, fake_db, candidate):
    resp = client.post("/auth/otp/request", json={"candidate_id": str(candidate.id), "phone": "   "})
    assert resp.status_code == 422


def _seed_otp(db: FakeDB, candidate: Candidate, code: str, *, expired=False, consumed=False, attempts=0):
    record = OtpCode(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        phone="+15551234567",
        code_hash=otp.hash_code(code),
        expires_at=datetime.now(timezone.utc) + (timedelta(minutes=-1) if expired else timedelta(minutes=5)),
        consumed_at=datetime.now(timezone.utc) if consumed else None,
        attempt_count=attempts,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    return record


def test_verify_otp_succeeds_with_correct_code(client, fake_db, candidate):
    _seed_otp(fake_db, candidate, "111111")
    resp = client.post("/auth/otp/verify", json={"candidate_id": str(candidate.id), "code": "111111"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True
    assert candidate.phone_verified_at is not None


def test_verify_otp_rejects_incorrect_code_and_increments_attempts(client, fake_db, candidate):
    record = _seed_otp(fake_db, candidate, "111111")
    resp = client.post("/auth/otp/verify", json={"candidate_id": str(candidate.id), "code": "999999"})
    assert resp.status_code == 400
    assert record.attempt_count == 1
    assert candidate.phone_verified_at is None


def test_verify_otp_rejects_expired_code(client, fake_db, candidate):
    _seed_otp(fake_db, candidate, "111111", expired=True)
    resp = client.post("/auth/otp/verify", json={"candidate_id": str(candidate.id), "code": "111111"})
    assert resp.status_code == 400


def test_verify_otp_rejects_already_consumed_code(client, fake_db, candidate):
    _seed_otp(fake_db, candidate, "111111", consumed=True)
    resp = client.post("/auth/otp/verify", json={"candidate_id": str(candidate.id), "code": "111111"})
    assert resp.status_code == 400


def test_verify_otp_rejects_after_max_attempts(client, fake_db, candidate):
    _seed_otp(fake_db, candidate, "111111", attempts=otp.MAX_VERIFY_ATTEMPTS)
    resp = client.post("/auth/otp/verify", json={"candidate_id": str(candidate.id), "code": "111111"})
    assert resp.status_code == 429


def test_verify_otp_with_no_request_on_file(client, fake_db, candidate):
    resp = client.post("/auth/otp/verify", json={"candidate_id": str(candidate.id), "code": "111111"})
    assert resp.status_code == 400


def test_verify_otp_uses_most_recently_requested_code(client, fake_db, candidate):
    import time

    _seed_otp(fake_db, candidate, "111111")
    time.sleep(0.01)
    _seed_otp(fake_db, candidate, "222222")

    # the older code should no longer work — only the latest request is active
    resp_old = client.post("/auth/otp/verify", json={"candidate_id": str(candidate.id), "code": "111111"})
    assert resp_old.status_code == 400

    resp_new = client.post("/auth/otp/verify", json={"candidate_id": str(candidate.id), "code": "222222"})
    assert resp_new.status_code == 200


def test_verify_otp_404_for_unknown_candidate(client, fake_db):
    resp = client.post("/auth/otp/verify", json={"candidate_id": str(uuid.uuid4()), "code": "111111"})
    assert resp.status_code == 404
