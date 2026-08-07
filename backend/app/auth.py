"""Sign in with Google.

Standard authorization-code flow, written against `requests` rather than an
OAuth library — it's three HTTP calls and the explicit version is easier to
audit than a framework's conventions.

Two deliberate choices:

* **Browsing never requires an account.** Every route here is additive; the
  map, the list and the API work signed out exactly as before. An account
  buys the things that genuinely need one (saved people, alerts), nothing else.
* **No passwords, ever.** Google holds the credential. The only thing stored
  is an opaque `sub`, plus a cached email/name for display.
"""
from __future__ import annotations

import base64
import binascii
import json
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db import get_session
from app.models import User
from app.schemas import UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "openid email profile"

_STATE_KEY = "oauth_state"
_USER_KEY = "uid"
_NEXT_KEY = "oauth_next"


def _safe_next(raw: str | None) -> str:
    """Sanitise a post-login return path.

    Only a same-origin path is ever accepted. `//evil.example` and
    `https://evil.example` are both browser-valid redirect targets, so
    anything that isn't a single leading slash is discarded rather than
    patched up — this is the classic open-redirect in OAuth callbacks.
    """
    if not raw or not raw.startswith("/") or raw.startswith("//"):
        return "/"
    if "\\" in raw or "\n" in raw or "\r" in raw:
        return "/"
    return raw


def _decode_id_token(id_token: str) -> dict:
    """Read the claims out of a Google ID token.

    The signature is deliberately not re-verified: this token arrives in the
    body of our own server-to-server HTTPS call to Google's token endpoint,
    which is exactly the case Google documents as not needing verification.
    A token pasted in by a client would need the full JWKS check — none is
    ever accepted here.
    """
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # restore stripped base64 padding
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError, binascii.Error) as exc:
        raise HTTPException(502, "Malformed identity token from Google") from exc


def current_user(
    request: Request, session: Session = Depends(get_session)
) -> User | None:
    """The signed-in user, or None. Never raises — anonymous is a valid state."""
    # With auth off there's no SessionMiddleware, and request.session asserts.
    if not config.AUTH_ENABLED:
        return None
    uid = request.session.get(_USER_KEY)
    if not uid:
        return None
    return session.get(User, uid)


def require_user(user: User | None = Depends(current_user)) -> User:
    """For routes that genuinely need an account."""
    if user is None:
        raise HTTPException(401, "Sign in to do that")
    return user


@router.get("/google/start")
def google_start(request: Request, next: str | None = None) -> RedirectResponse:
    if not config.AUTH_ENABLED:
        raise HTTPException(503, "Google sign-in isn't configured on this server")

    # State ties the callback to this browser session — without it, an
    # attacker can complete a login in someone else's browser.
    state = secrets.token_urlsafe(24)
    request.session[_STATE_KEY] = state
    # Kept server-side rather than round-tripped through Google, so it can't
    # be tampered with in transit.
    request.session[_NEXT_KEY] = _safe_next(next)

    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.OAUTH_REDIRECT_URL,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
def google_callback(
    request: Request,
    session: Session = Depends(get_session),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if not config.AUTH_ENABLED:
        raise HTTPException(503, "Google sign-in isn't configured on this server")

    expected = request.session.pop(_STATE_KEY, None)
    nxt = _safe_next(request.session.pop(_NEXT_KEY, None))
    if error:
        # User hit "cancel" — not an error worth a stack trace.
        return RedirectResponse(f"{config.WEB_ORIGIN}{nxt}")
    if not code or not state or not expected or not secrets.compare_digest(state, expected):
        raise HTTPException(400, "Sign-in could not be verified — please try again")

    token_resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.OAUTH_REDIRECT_URL,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if not token_resp.ok:
        raise HTTPException(502, "Google rejected the sign-in")

    claims = _decode_id_token(token_resp.json().get("id_token", ""))
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(502, "Google returned no account id")
    if not claims.get("email_verified", False):
        raise HTTPException(403, "Your Google email address isn't verified")

    now = datetime.now(timezone.utc)
    user = session.scalars(select(User).where(User.google_sub == sub)).one_or_none()
    if user is None:
        user = User(google_sub=sub, created_at=now, last_login_at=now)
        session.add(user)
    # Refreshed every sign-in: people rename themselves and change addresses.
    user.email = claims.get("email", "")
    user.name = claims.get("name", "")
    user.picture = claims.get("picture", "")
    user.last_login_at = now
    session.commit()

    # New session id after a privilege change — stops session fixation.
    request.session.clear()
    request.session[_USER_KEY] = user.id
    return RedirectResponse(f"{config.WEB_ORIGIN}{nxt}")


@router.get("/me", response_model=UserOut | None)
def me(user: User | None = Depends(current_user)) -> UserOut | None:
    if user is None:
        return None
    return UserOut(
        id=user.id, email=user.email, name=user.name, picture=user.picture
    )


@router.delete("/me")
def delete_account(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    """Remove the account and everything hanging off it.

    Feature tables declare ON DELETE CASCADE against users.id, so this is one
    statement rather than a list that drifts as features are added.
    """
    session.delete(user)
    session.commit()
    request.session.clear()
    return {"deleted": True}


@router.post("/logout")
def logout(request: Request) -> dict:
    if config.AUTH_ENABLED:
        request.session.clear()
    return {"ok": True}


@router.get("/config")
def auth_config() -> dict:
    """Lets the UI hide the sign-in button when the server can't honour it."""
    return {"enabled": config.AUTH_ENABLED}
