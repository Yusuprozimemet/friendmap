"""Saved-search alerts.

The unsubscribe token is the security-relevant part: it arrives from an email
client with no session behind it, so the signature is the *only* thing stopping
one person switching off another's alerts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app import alerts, config, mail
from app.models import AlertSent, SavedSearch
from tests.conftest import make_post, make_profile, make_user

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
#
# These build the whole precondition — user, saved search, matching profile —
# because the bug this section exists for was an early `return 0` that every
# cheaper test walked straight past.

def _due_search(session, user, **over):
    fields = {
        "user_id": user.id,
        "name": "Climbers",
        "filters": {},
        "cadence": "daily",
        "last_run_at": None,
        "created_at": NOW,
    }
    fields.update(over)
    row = SavedSearch(**fields)
    session.add(row)
    session.flush()
    return row


def _matching_person(session, reddit_id="alrt01", author="alice"):
    post = make_post(session, reddit_id, author=author, days_ago=1)
    return make_profile(session, post, age=30, interests=("hiking",))


@pytest.fixture
def sent(monkeypatch):
    """Capture what would be mailed instead of sending it."""
    box: list[tuple[str, str, str]] = []
    monkeypatch.setattr(mail, "send", lambda to, subject, body: (
        box.append((to, subject, body)) or True
    ))
    return box


def test_a_due_search_with_a_match_sends_one_digest(session, sent):
    """The regression test for the gate.

    This is the scheduled job's exact situation: no Google credentials in the
    environment (so AUTH_ENABLED is false), but a real account with a real
    saved search that matches somebody. It must still send.
    """
    assert config.AUTH_ENABLED is False, "the ingest container never has OAuth set"

    user = make_user(session, email="me@example.com")
    _due_search(session, user)
    _matching_person(session)
    session.commit()

    assert alerts.run_alerts(session, NOW) == 1
    assert len(sent) == 1
    to, subject, _ = sent[0]
    assert to == "me@example.com"
    assert "1 new person" in subject


def test_no_digest_without_a_session_secret(session, sent):
    """Unsubscribe links could not be signed, so sending is worse than not."""
    user = make_user(session)
    _due_search(session, user)
    _matching_person(session)
    session.commit()

    original = config.SESSION_SECRET
    try:
        config.SESSION_SECRET = ""
        assert alerts.run_alerts(session, NOW) == 0
    finally:
        config.SESSION_SECRET = original
    assert sent == []


def test_digest_body_links_are_well_formed(session, sent):
    """No double slashes, whatever WEB_ORIGIN was set to."""
    user = make_user(session)
    search = _due_search(session, user)
    _matching_person(session)
    session.commit()

    alerts.run_alerts(session, NOW)
    _, _, body = sent[0]
    assert "//api/alerts/unsubscribe" not in body
    assert f"{config.WEB_ORIGIN}/api/alerts/unsubscribe?token=" in body
    # And the token in the mail actually resolves to this search.
    token = body.split("token=")[1].split()[0]
    assert alerts.read_unsubscribe_token(token) == search.id


def test_a_person_is_only_announced_once(session, sent):
    """Second run has nothing new, so it must stay quiet."""
    user = make_user(session)
    _due_search(session, user)
    _matching_person(session)
    session.commit()

    assert alerts.run_alerts(session, NOW) == 1
    # A day later the same person is still matching, but already announced.
    assert alerts.run_alerts(session, NOW + timedelta(days=1)) == 0
    assert len(sent) == 1


def test_a_failed_send_is_not_recorded_so_tomorrow_retries(session, monkeypatch):
    """alerts_sent is written only after a successful hand-off."""
    monkeypatch.setattr(mail, "send", lambda to, subject, body: False)

    user = make_user(session)
    _due_search(session, user)
    _matching_person(session)
    session.commit()

    assert alerts.run_alerts(session, NOW) == 0
    assert session.scalar(select(func.count()).select_from(AlertSent)) == 0

    # Transport recovers; the person is still owed an announcement.
    box: list = []
    monkeypatch.setattr(mail, "send", lambda to, subject, body: (
        box.append(to) or True
    ))
    assert alerts.run_alerts(session, NOW + timedelta(days=1)) == 1


def test_one_digest_per_user_not_per_search(session, sent):
    """Three saved searches finding someone must not be three emails."""
    user = make_user(session)
    for i in range(3):
        _due_search(session, user, name=f"search {i}")
    _matching_person(session)
    session.commit()

    assert alerts.run_alerts(session, NOW) == 1
    assert len(sent) == 1
    assert "your saved searches" in sent[0][1]


def test_last_run_advances_even_with_nothing_to_report(session, sent):
    """Otherwise a quiet search re-runs on every job forever."""
    user = make_user(session)
    search = _due_search(session, user)
    session.commit()  # no people at all

    assert alerts.run_alerts(session, NOW) == 0
    session.refresh(search)
    assert search.last_run_at is not None


def test_a_switched_off_search_is_left_alone(session, sent):
    user = make_user(session)
    _due_search(session, user, cadence="off")
    _matching_person(session)
    session.commit()

    assert alerts.run_alerts(session, NOW) == 0
    assert sent == []
