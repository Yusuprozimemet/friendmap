"""Stable, non-reversible identity for the people on the map.

There is no `people` table by design — people are grouped by author at query
time — so `Person.id` is a *post* id, and it changes the moment someone posts
again. Anything a user attaches to a person (a save, a note, "already
contacted") therefore cannot key on it, or it silently detaches on their next
post.

The author's username would be stable, but it was deliberately removed from
the API. So we key on it without revealing it.

HMAC rather than a plain hash on purpose: Reddit usernames are a small,
enumerable space, and `sha256(username)` would be trivially reversible with a
wordlist. Keyed, it isn't.
"""
from __future__ import annotations

import hashlib
import hmac

from app import config

#: 24 hex chars = 96 bits. Collision odds across a few million people are
#: negligible, and it keeps URLs and JSON readable.
_KEY_LENGTH = 24


def person_key(author: str) -> str:
    """Stable id for a person, or "" when there's nothing to key on.

    Empty for deleted Reddit accounts (no author) and when no secret is
    configured — callers treat "" as "this person can't be saved".
    """
    author = (author or "").strip().lower()
    if not author or not config.PERSON_KEY_SECRET:
        return ""
    return hmac.new(
        config.PERSON_KEY_SECRET.encode(),
        author.encode(),
        hashlib.sha256,
    ).hexdigest()[:_KEY_LENGTH]
