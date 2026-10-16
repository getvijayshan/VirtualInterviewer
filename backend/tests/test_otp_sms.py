import httpx
import pytest

from app.config import settings
from app.services import otp


def _resp(status=200, body=None):
    return httpx.Response(status, json=body if body is not None else {"return": True})


@pytest.fixture
def fast2sms(monkeypatch):
    monkeypatch.setattr(settings, "sms_provider", "fast2sms")
    monkeypatch.setattr(settings, "fast2sms_api_key", "key123")


@pytest.mark.parametrize("raw", ["9876543210", "+91 98765 43210", "919876543210", "09876543210"])
def test_phone_normalised_to_ten_digits(raw):
    assert otp._indian_mobile(raw) == "9876543210"


@pytest.mark.parametrize("raw", ["12345", "5876543210", "+1 415 555 0100"])
def test_non_indian_numbers_rejected(raw):
    with pytest.raises(otp.SmsDeliveryError):
        otp._indian_mobile(raw)


def test_fast2sms_request_shape(fast2sms, monkeypatch):
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return _resp()

    monkeypatch.setattr(otp.httpx, "post", fake_post)
    otp.send_otp("+91 98765 43210", "123456")
    assert seen["headers"] == {"authorization": "key123"}
    assert seen["json"] == {"route": "otp", "variables_values": "123456", "numbers": "9876543210"}


def test_provider_rejection_raises(fast2sms, monkeypatch):
    monkeypatch.setattr(otp.httpx, "post", lambda *a, **k: _resp(400, {"return": False, "message": "bad"}))
    with pytest.raises(otp.SmsDeliveryError):
        otp.send_otp("9876543210", "123456")


def test_network_failure_raises(fast2sms, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(otp.httpx, "post", boom)
    with pytest.raises(otp.SmsDeliveryError):
        otp.send_otp("9876543210", "123456")


def test_no_provider_only_logs(monkeypatch, capsys):
    monkeypatch.setattr(settings, "sms_provider", "")
    otp.send_otp("9876543210", "123456")
    assert "would SMS" in capsys.readouterr().out
