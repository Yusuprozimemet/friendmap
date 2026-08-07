"""The database URL rewrite.

This is the one dialect-dependent thing in the app and it fails *late* — a bare
`postgresql://` makes SQLAlchemy reach for psycopg2, which isn't installed, so
the error arrives at the first query rather than at startup. CI's smoke job
covers the same rewrite against a real Postgres; this covers the string forms.
"""
from __future__ import annotations

import pytest

from app.config import _normalise_db_url


@pytest.mark.parametrize(
    "given,expected",
    [
        # What Render, Heroku and Fly hand out.
        (
            "postgres://u:p@host:5432/db",
            "postgresql+psycopg://u:p@host:5432/db",
        ),
        (
            "postgresql://u:p@host:5432/db",
            "postgresql+psycopg://u:p@host:5432/db",
        ),
        # Already explicit — must not be rewritten twice.
        (
            "postgresql+psycopg://u:p@host:5432/db",
            "postgresql+psycopg://u:p@host:5432/db",
        ),
        # Query strings (sslmode) survive.
        (
            "postgres://u:p@host/db?sslmode=require",
            "postgresql+psycopg://u:p@host/db?sslmode=require",
        ),
        # Other dialects are left alone.
        ("sqlite+pysqlite:///./local.db", "sqlite+pysqlite:///./local.db"),
    ],
)
def test_normalise_db_url(given, expected):
    assert _normalise_db_url(given) == expected


def test_password_containing_the_prefix_is_not_mangled():
    """Only the scheme is rewritten — `startswith`, not a global replace."""
    url = "postgres://user:postgres://weird@host/db"
    assert _normalise_db_url(url) == "postgresql+psycopg://user:postgres://weird@host/db"


# --- WEB_ORIGIN -----------------------------------------------------------
# Everything downstream appends a path starting with "/", so a trailing slash
# on the setting produced "https://host//api/alerts/unsubscribe" — a 404 that
# only shows up when somebody clicks a link in an email.

def test_web_origin_has_no_trailing_slash(monkeypatch):
    import importlib

    from app import config as config_module

    for given, expected in [
        ("https://example.onrender.com/", "https://example.onrender.com"),
        ("https://example.onrender.com", "https://example.onrender.com"),
        ("https://example.onrender.com///", "https://example.onrender.com"),
        ("http://localhost:5173/", "http://localhost:5173"),
    ]:
        monkeypatch.setenv("WEB_ORIGIN", given)
        reloaded = importlib.reload(config_module)
        assert reloaded.WEB_ORIGIN == expected

    # Leave the module as the rest of the suite expects it.
    monkeypatch.delenv("WEB_ORIGIN", raising=False)
    monkeypatch.setenv("WEB_ORIGIN", "http://testserver")
    importlib.reload(config_module)
