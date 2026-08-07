"""Saved-search alerts.

The unsubscribe token is the security-relevant part: it arrives from an email
client with no session behind it, so the signature is the *only* thing stopping
one person switching off another's alerts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import alerts, config
from app.models import SavedSearch

NOW = datetime(2026, 8, 7, 6, 30, tzinfo=timezone.utc)


def search(*, cadence: str = "daily", last_run_at: datetime | None = None) -> SavedSearch:
    return SavedSearch(
        id=1,
        user_id=1,
        name="Climbers in Utrecht",
        filters={},
        cadence=cadence,
        last_run_at=last_run_at,
        created_at=NOW,
    )


# --- unsubscribe tokens ---------------------------------------------------

def test_token_round_trip():
    assert alerts.read_unsubscribe_token(alerts.unsubscribe_token(42)) == 42


def test_token_is_rejected_when_tampered_with():
    token = alerts.unsubscribe_token(42)
    # Flip a character in the payload. The signature no longer matches, so the
    # token can't be pointed at a different saved search.
    tampered = ("X" if token[0] != "X" else "Y") + token[1:]
    assert alerts.read_unsubscribe_token(tampered) is None


def test_garbage_token_is_rejected():
    for junk in ("", "not-a-token", "a.b.c", "x" * 200):
        assert alerts.read_unsubscribe_token(junk) is None


def test_token_from_a_different_secret_is_rejected():
    """Rotating SESSION_SECRET must invalidate old links, not accept them."""
    original = config.SESSION_SECRET
    try:
        config.SESSION_SECRET = "secret-a"
        token = alerts.unsubscribe_token(42)
        config.SESSION_SECRET = "secret-b"
        assert alerts.read_unsubscribe_token(token) is None
    finally:
        config.SESSION_SECRET = original


def test_token_is_salted_against_the_session_cookie():
    """Same secret, different purpose. A session cookie must not be usable as
    an unsubscribe token or vice versa."""
    from itsdangerous import URLSafeSerializer

    unsalted = URLSafeSerializer(config.SESSION_SECRET).dumps({"sid": 42})
    assert alerts.read_unsubscribe_token(unsalted) is None


def test_token_payload_must_carry_an_int_id():
    """A string id would reach `session.get(SavedSearch, "1")`."""
    from itsdangerous import URLSafeSerializer

    forged = URLSafeSerializer(
        config.SESSION_SECRET, salt="friendmap-alert-unsubscribe"
    ).dumps({"sid": "1"})
    assert alerts.read_unsubscribe_token(forged) is None


# --- cadence --------------------------------------------------------------

def test_never_run_is_due():
    assert alerts._is_due(search(last_run_at=None), NOW) is True


def test_off_is_never_due():
    """Even a search that has never run stays quiet when switched off."""
    assert alerts._is_due(search(cadence="off", last_run_at=None), NOW) is False
    assert alerts._is_due(search(cadence="off", last_run_at=NOW - timedelta(days=30)), NOW) is False


def test_unknown_cadence_is_never_due():
    assert alerts._is_due(search(cadence="hourly"), NOW) is False


@pytest.mark.parametrize(
    "cadence,hours_since,expected",
    [
        ("daily", 1, False),
        ("daily", 23, True),    # the one-hour grace window
        ("daily", 24, True),
        ("weekly", 24, False),
        ("weekly", 167, True),  # 7 days less an hour
        ("weekly", 168, True),
    ],
)
def test_due_respects_cadence_with_an_hour_of_grace(cadence, hours_since, expected):
    """The grace window matters: the job runs on a cron, and consecutive runs
    drift a few minutes. Without it a daily alert would skip every other day.
    """
    last = NOW - timedelta(hours=hours_since)
    assert alerts._is_due(search(cadence=cadence, last_run_at=last), NOW) is expected


def test_naive_last_run_is_treated_as_utc():
    """Columns read back without a timezone must not raise on subtraction."""
    naive = (NOW - timedelta(days=2)).replace(tzinfo=None)
    assert alerts._is_due(search(cadence="daily", last_run_at=naive), NOW) is True


# --- the job --------------------------------------------------------------

def test_run_alerts_is_a_no_op_when_auth_is_disabled(session):
    """No accounts means no addresses to send to."""
    assert config.AUTH_ENABLED is False
    assert alerts.run_alerts(session, NOW) == 0
