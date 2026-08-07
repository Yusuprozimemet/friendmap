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
