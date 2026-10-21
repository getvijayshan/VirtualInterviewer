"""FL-06: OAuth sign-in with Google and LinkedIn (authorization-code flow).

The backend owns the whole flow: start() builds the provider URL, the callback
exchanges the code and reads the verified email. `state` is an HMAC-signed,
short-lived token carrying the session being authenticated, so the callback
needs no server-side storage and can't be forged or replayed across sessions.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

STATE_TTL_SECONDS = 600


class OAuthError(Exception):
    """Sign-in failed; the message is safe to show the user."""


@dataclass(frozen=True)
class Provider:
    name: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str

    @property
    def client_id(self) -> str:
        return getattr(settings, f"{self.name}_client_id")

    @property
    def client_secret(self) -> str:
        return getattr(settings, f"{self.name}_client_secret")

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def redirect_uri(self) -> str:
        return f"{settings.api_public_url.rstrip('/')}/auth/oauth/{self.name}/callback"


PROVIDERS = {
    "google": Provider(
        name="google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scope="openid email profile",
    ),
    "linkedin": Provider(
        name="linkedin",
        authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",
        userinfo_url="https://api.linkedin.com/v2/userinfo",
        scope="openid profile email",
    ),
}


def get_provider(name: str) -> Provider:
    provider = PROVIDERS.get(name)
    if provider is None or not provider.enabled or not settings.auth_secret:
        raise OAuthError("This sign-in method is not available.")
    return provider


def enabled_providers() -> list[str]:
    if not settings.auth_secret:
        return []
    return [name for name, p in PROVIDERS.items() if p.enabled]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _sign(payload: str) -> str:
    return _b64(hmac.new(settings.auth_secret.encode(), payload.encode(), hashlib.sha256).digest())


def make_state(provider: str, session_id: str) -> str:
    payload = _b64(json.dumps({"p": provider, "s": session_id, "exp": int(time.time()) + STATE_TTL_SECONDS}).encode())
    return f"{payload}.{_sign(payload)}"


def read_state(state: str, provider: str) -> str:
    """Return the session id the state was issued for, or raise OAuthError."""
    try:
        payload, sig = state.split(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            raise ValueError("bad signature")
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if data["p"] != provider or data["exp"] < time.time():
            raise ValueError("wrong provider or expired")
        return data["s"]
    except (ValueError, KeyError, json.JSONDecodeError):
        raise OAuthError("Sign-in link expired or invalid. Please try again.") from None


def authorize_url(provider: Provider, state: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": provider.client_id,
            "redirect_uri": provider.redirect_uri,
            "scope": provider.scope,
            "state": state,
        }
    )
    return f"{provider.authorize_url}?{query}"


def fetch_verified_email(provider: Provider, code: str) -> str:
    """Exchange the authorization code and return the user's verified email."""
    try:
        token_resp = httpx.post(
            provider.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": provider.redirect_uri,
                "client_id": provider.client_id,
                "client_secret": provider.client_secret,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        info_resp = httpx.get(
            provider.userinfo_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10
        )
        info_resp.raise_for_status()
        info = info_resp.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.error("%s OAuth exchange failed: %s", provider.name, exc)
        raise OAuthError("Could not sign in. Please try again.") from exc

    email = info.get("email")
    # Google returns a bool; LinkedIn has returned it as a bool too, but accept the string form.
    verified = info.get("email_verified") in (True, "true")
    if not email or not verified:
        raise OAuthError("Your account has no verified email address.")
    return email
