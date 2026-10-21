import time
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Candidate, InterviewSession
from app.services import oauth
from tests.test_auth_router import FakeDB


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", "test-secret")
    monkeypatch.setattr(settings, "google_client_id", "gid")
    monkeypatch.setattr(settings, "google_client_secret", "gsecret")
    monkeypatch.setattr(settings, "linkedin_client_id", "")
    monkeypatch.setattr(settings, "linkedin_client_secret", "")
    monkeypatch.setattr(settings, "api_public_url", "https://app.test/api")
    monkeypatch.setattr(settings, "frontend_public_url", "https://app.test")


@pytest.fixture
def world():
    candidate = Candidate(id=uuid.uuid4(), name="Jane", email=None)
    session = InterviewSession(id=uuid.uuid4(), candidate_id=candidate.id)
    db = FakeDB(seed=[candidate, session])
    app.dependency_overrides[get_db] = lambda: db
    yield candidate, session
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


def test_methods_lists_only_configured_providers(client):
    assert client.get("/auth/methods").json() == {"oauth_providers": ["google"]}


def test_methods_empty_without_auth_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", "")
    assert client.get("/auth/methods").json() == {"oauth_providers": []}


def test_start_returns_provider_url_with_signed_state(client, world):
    _, session = world
    resp = client.get(f"/auth/oauth/google/start?session_id={session.id}")
    assert resp.status_code == 200
    url = urlparse(resp.json()["authorize_url"])
    q = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert q["client_id"] == ["gid"]
    assert q["redirect_uri"] == ["https://app.test/api/auth/oauth/google/callback"]
    assert oauth.read_state(q["state"][0], "google") == str(session.id)


def test_start_404_for_unconfigured_provider(client, world):
    _, session = world
    assert client.get(f"/auth/oauth/linkedin/start?session_id={session.id}").status_code == 404


def test_state_rejects_tampering_wrong_provider_and_expiry(monkeypatch):
    state = oauth.make_state("google", "abc")
    with pytest.raises(oauth.OAuthError):
        oauth.read_state(state + "x", "google")
    with pytest.raises(oauth.OAuthError):
        oauth.read_state(state, "linkedin")
    later = time.time() + oauth.STATE_TTL_SECONDS + 1
    monkeypatch.setattr(oauth.time, "time", lambda: later)
    with pytest.raises(oauth.OAuthError):
        oauth.read_state(state, "google")


def test_callback_verifies_candidate_and_redirects_to_report(client, world, monkeypatch):
    candidate, session = world
    monkeypatch.setattr(oauth, "fetch_verified_email", lambda prov, code: "jane@gmail.com")
    state = oauth.make_state("google", str(session.id))

    resp = client.get(f"/auth/oauth/google/callback?code=abc&state={state}")

    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == f"https://app.test/sessions/{session.id}/report"
    assert candidate.verified_at is not None
    assert candidate.auth_provider == "google"
    assert candidate.email == "jane@gmail.com"


def test_callback_denied_redirects_back_to_gate_unverified(client, world):
    candidate, session = world
    state = oauth.make_state("google", str(session.id))
    resp = client.get(f"/auth/oauth/google/callback?error=access_denied&state={state}")
    assert resp.headers["location"].startswith(f"https://app.test/sessions/{session.id}/auth?error=")
    assert candidate.verified_at is None


def test_callback_with_bad_state_never_verifies(client, world):
    candidate, _ = world
    resp = client.get("/auth/oauth/google/callback?code=abc&state=garbage")
    assert "auth_error" in resp.headers["location"]
    assert candidate.verified_at is None


def test_unverified_provider_email_is_rejected(monkeypatch):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"access_token": "t", "email": "a@b.c", "email_verified": False}

    monkeypatch.setattr(oauth.httpx, "post", lambda *a, **k: R())
    monkeypatch.setattr(oauth.httpx, "get", lambda *a, **k: R())
    with pytest.raises(oauth.OAuthError):
        oauth.fetch_verified_email(oauth.PROVIDERS["google"], "code")
