from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app


def test_cors_origins_default_to_local_dev_server():
    assert Settings(cors_allowed_origins="").cors_origins == ["http://localhost:3000"]


def test_cors_origins_parse_comma_separated_list():
    s = Settings(cors_allowed_origins="https://a.example, https://b.example ,")
    assert s.cors_origins == ["https://a.example", "https://b.example"]


def test_preflight_allows_local_dev_origin():
    res = TestClient(app).options(
        "/resumes",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
