"""Test fixtures.

Two things have to happen before anything under `app.` is imported, and both
are why this file does work at module scope rather than in fixtures:

1. **The environment is pinned.** `app/config.py` runs `load_dotenv()` at
   import time, so a developer's real `friendsMap/.env` would otherwise decide
   what the tests see — including whether auth is enabled, which changes the
   middleware stack. `load_dotenv` does not override variables that are
   already set, so setting them here wins.
2. **`DATABASE_URL` points at a throwaway SQLite file.** `app/db.py` builds
   the engine at import time from that value, so it cannot be redirected
   afterwards.

SQLite is enough because the schema uses no Postgres-specific types — the only
dialect-dependent thing is the `postgres://` → psycopg rewrite, and CI's
separate smoke job exercises that against a real Postgres 16.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="friendmap-tests-"))

os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_TMP / 'test.db'}"
# Fixed, not random: the person-key tests assert a *stable* digest, which is
# the property the whole saved-people feature depends on.
os.environ["PERSON_KEY_SECRET"] = "test-person-key-secret"
os.environ["SESSION_SECRET"] = "test-session-secret"
# Auth off by default. `AUTH_ENABLED` is computed at import and decides whether
# SessionMiddleware is installed, so it must be settled before `app.main`
# loads; the signed-in cases construct rows directly instead.
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["MAIL_BACKEND"] = "console"
os.environ["WEB_ORIGIN"] = "http://testserver"
os.environ["TRUST_PROXY"] = "false"

# Imported after the environment is pinned above — see the module docstring.
# E402 is suppressed rather than worked around: the import order *is* the
# fixture here, and moving these to the top would silently reintroduce the
# developer's own .env.
from app.db import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Interest,
    Place,
    Post,
    Profile,
    User,
)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(_schema):
    """A session on an empty database.

    Tables are emptied rather than recreated per test: `create_all` on every
    test is the slowest part of a suite this size, and truncating is exact.
    """
    with SessionLocal() as s:
        for table in reversed(Base.metadata.sorted_tables):
            s.execute(table.delete())
        s.commit()
        yield s


@pytest.fixture
def client(session):
    """TestClient sharing the test's session.

    The dependency override matters: without it the route opens its own
    session against the same file and wouldn't see uncommitted fixture rows.
    """
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --- row builders ---------------------------------------------------------
# Plain functions, not factory-boy: the schema has half a dozen non-null
# timestamp columns and spelling out the defaults once here is less machinery
# than a library.

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_post(
    session,
    reddit_id: str,
    *,
    author: str = "someone",
    subreddit: str = "makenewfriendsNL",
    title: str = "Hi everyone",
    body: str = "Looking to meet people.",
    days_ago: int = 1,
    deleted: bool = False,
) -> Post:
    now = utcnow()
    post = Post(
        reddit_id=reddit_id,
        subreddit=subreddit,
        author=author,
        title=title,
        body=body,
        url=f"https://reddit.com/r/{subreddit}/comments/{reddit_id}",
        posted_at=now - timedelta(days=days_ago),
        scraped_at=now,
        last_seen_at=now,
        deleted_at=now if deleted else None,
    )
    session.add(post)
    session.flush()
    return post


def make_place(
    session,
    name: str = "Amsterdam",
    *,
    kind: str = "city",
    province: str = "Noord-Holland",
    lat: float = 52.3676,
    lon: float = 4.9041,
) -> Place:
    place = Place(name=name, kind=kind, province=province, lat=lat, lon=lon)
    session.add(place)
    session.flush()
    return place


def make_profile(
    session,
    post: Post,
    *,
    age: int | None = 30,
    gender: str = "F",
    place: Place | None = None,
    geo_precision: str = "city",
    post_type: str = "profile",
    lang: str = "en",
    summary: str = "Climbs twice a week and wants a regular partner.",
    interests: tuple[str, ...] = (),
    needs_review: bool = False,
    location_raw: str | None = None,
) -> Profile:
    profile = Profile(
        post_id=post.reddit_id,
        age=age,
        gender=gender,
        place_id=place.id if place else None,
        geo_precision=geo_precision,
        post_type=post_type,
        lang=lang,
        summary=summary,
        location_raw=location_raw,
        confidence=0.9,
        needs_review=needs_review,
        model="test",
        extracted_at=utcnow(),
    )
    # Added before the interests are appended: appending across the
    # relationship on a detached object makes SQLAlchemy skip the association
    # row (and warn), so the tags would silently not be attached.
    session.add(profile)
    session.flush()
    for slug in interests:
        row = session.query(Interest).filter_by(slug=slug).one_or_none()
        if row is None:
            row = Interest(slug=slug)
            session.add(row)
            session.flush()
        profile.interests.append(row)
    session.flush()
    return profile


def make_user(session, email: str = "someone@example.com", sub: str = "g-1") -> User:
    now = utcnow()
    user = User(
        google_sub=sub,
        email=email,
        name="Test Person",
        created_at=now,
        last_login_at=now,
    )
    session.add(user)
    session.flush()
    return user
