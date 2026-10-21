import smtplib

import pytest

from app.config import settings
from app.services import otp


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
        self.started_tls = False
        self.logged_in = None
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        self.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "bot@example.com")
    monkeypatch.setattr(settings, "smtp_password", "pw")
    monkeypatch.setattr(settings, "smtp_from", "")
    monkeypatch.setattr(otp.smtplib, "SMTP", FakeSMTP)


def test_sends_code_over_starttls_smtp(smtp):
    otp.send_otp("jane@example.com", "123456")
    server = FakeSMTP.instances[0]
    assert server.started_tls
    assert server.logged_in == ("bot@example.com", "pw")
    msg = server.sent[0]
    assert msg["To"] == "jane@example.com"
    assert msg["From"] == "bot@example.com"
    assert "123456" in msg.get_content()


def test_smtp_failure_raises(smtp, monkeypatch):
    def boom(*a, **k):
        raise smtplib.SMTPException("down")

    monkeypatch.setattr(otp.smtplib, "SMTP", boom)
    with pytest.raises(otp.EmailDeliveryError):
        otp.send_otp("jane@example.com", "123456")


def test_no_smtp_host_only_logs(monkeypatch, capsys):
    monkeypatch.setattr(settings, "smtp_host", "")
    otp.send_otp("jane@example.com", "123456")
    assert "would email" in capsys.readouterr().out
