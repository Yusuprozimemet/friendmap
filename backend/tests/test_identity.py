"""Person keys.

Two properties, both load-bearing:

* **Stable** — every save, note and alert row hangs off this value. If it
  changed, every one of them would silently detach.
* **Not reversible** — it stands in for a username that was deliberately kept
  out of the API. A plain hash of a Reddit username is trivially reversible
  with a wordlist, so this is keyed.
"""
from __future__ import annotations

from app import config, identity
from app.identity import person_key


def test_is_stable_for_the_same_author():
    assert person_key("someone") == person_key("someone")


def test_is_case_and_whitespace_insensitive():
    """Reddit usernames are case-insensitive; the key must agree."""
    assert person_key("SomeOne") == person_key("someone")
    assert person_key("  someone  ") == person_key("someone")


def test_differs_between_authors():
    assert person_key("alice") != person_key("bob")


def test_length_and_alphabet():
    key = person_key("someone")
    assert len(key) == 24
    assert all(c in "0123456789abcdef" for c in key)


def test_empty_for_a_deleted_account():
    """No author to key on — callers read "" as "can't be saved"."""
    assert person_key("") == ""
    assert person_key(None) == ""
    assert person_key("   ") == ""


def test_empty_when_no_secret_is_configured():
    """Better to disable saving than to hand out unkeyed, reversible hashes."""
    original = config.PERSON_KEY_SECRET
    try:
        config.PERSON_KEY_SECRET = ""
        assert person_key("someone") == ""
    finally:
        config.PERSON_KEY_SECRET = original


def test_the_key_actually_depends_on_the_secret():
    """Guards against the HMAC being replaced by a bare digest.

    A plain `sha256(username)` would satisfy every test above.
    """
    original = config.PERSON_KEY_SECRET
    try:
        config.PERSON_KEY_SECRET = "secret-a"
        with_a = person_key("someone")
        config.PERSON_KEY_SECRET = "secret-b"
        with_b = person_key("someone")
    finally:
        config.PERSON_KEY_SECRET = original
    assert with_a != with_b


def test_is_not_a_bare_sha256_of_the_username():
    import hashlib

    assert person_key("someone") != hashlib.sha256(b"someone").hexdigest()[:24]


def test_fits_the_column():
    """`user_people.person_key` is String(24) — the key must not be truncated."""
    assert identity._KEY_LENGTH == 24
