"""Erasure, suppression and retention.

The property that matters: a removal has to survive tomorrow's scrape. Deleting
the row alone does not achieve that, because the post is still live on Reddit —
so the interesting tests here all re-run the scrape's write path afterwards and
assert the data stayed gone.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.identity import person_key
from app.models import Post, Profile, Suppression
from ingest import store
from tests.conftest import make_post, make_profile

NOW = datetime.now(timezone.utc)


def scraped(reddit_id="sup001", author="alice", days_ago=1):
    """A post in the shape `upsert_posts` receives from the scraper."""
    return {
        "id": reddit_id,
        "subreddit": "makenewfriendsNL",
        "author": author,
        "title": "Hi",
        "body": "Looking to meet people.",
        "url": f"https://reddit.com/r/makenewfriendsNL/comments/{reddit_id}",
        "posted_at": NOW - timedelta(days=days_ago),
    }


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


# --- suppression by post --------------------------------------------------

def test_suppressing_a_post_deletes_it_and_its_profile(session):
    post = make_post(session, "gone01", author="alice")
    make_profile(session, post)
    session.commit()

    deleted, added = store.suppress(session, reddit_id="gone01", reason="emailed")
    assert (deleted, added) == (1, 1)
    assert count(session, Post) == 0
    # The profile cascades — an orphaned profile would still hold the summary.
    assert count(session, Profile) == 0


def test_a_suppressed_post_is_not_re_added_by_the_next_scrape(session):
    """The whole point. Without the suppression row this comes straight back."""
    store.suppress(session, reddit_id="sup001")
    new_ids = store.upsert_posts(session, [scraped("sup001")])
    assert new_ids == []
    assert count(session, Post) == 0


def test_other_posts_in_the_same_scrape_are_unaffected(session):
    store.suppress(session, reddit_id="sup001")
    new_ids = store.upsert_posts(
        session, [scraped("sup001"), scraped("keep01", author="bob")]
    )
    assert new_ids == ["keep01"]
    assert count(session, Post) == 1


def test_suppression_is_idempotent(session):
    store.suppress(session, reddit_id="sup001", reason="first")
    _, added = store.suppress(session, reddit_id="sup001", reason="again")
    assert added == 0
    assert count(session, Suppression) == 1


# --- suppression by person ------------------------------------------------

def test_suppressing_a_person_removes_every_post_they_have(session):
    for i in range(3):
        make_profile(session, make_post(session, f"al{i:04}", author="alice"))
    make_profile(session, make_post(session, "bob001", author="bob"))
    session.commit()

    deleted, _ = store.suppress(session, author="alice", reason="asked by email")
    assert deleted == 3
    assert [p.author for p in session.scalars(select(Post)).all()] == ["bob"]


def test_suppressing_a_person_blocks_posts_they_have_not_written_yet(session):
    """"Take me off this site" has to mean future posts too, or the next one
    they write reinstates them."""
    store.suppress(session, author="alice")
    new_ids = store.upsert_posts(
        session, [scraped("fut001", author="alice"), scraped("oth001", author="bob")]
    )
    assert new_ids == ["oth001"]


def test_person_suppression_is_case_insensitive(session):
    """Reddit usernames are case-insensitive; the key already folds case."""
    store.suppress(session, author="Alice")
    assert store.upsert_posts(session, [scraped("cas001", author="alice")]) == []


def test_the_username_is_not_stored_in_the_suppression(session):
    """Honouring the request must not require keeping their name on file."""
    store.suppress(session, author="alice")
    row = session.scalars(select(Suppression)).one()
    assert row.person_key == person_key("alice")
    assert "alice" not in (row.person_key or "")
    assert row.reddit_id is None


def test_suppress_needs_a_target(session):
    with pytest.raises(ValueError, match="either reddit_id or author"):
        store.suppress(session)


def test_deleted_accounts_are_not_all_suppressed_together(session):
    """An empty author must not become a key that matches every anonymous post."""
    store.suppress(session, reddit_id="sup001")
    # person_key("") is "", and the filter must not treat that as a match.
    new_ids = store.upsert_posts(session, [scraped("anon01", author="")])
    assert new_ids == ["anon01"]


# --- retention ------------------------------------------------------------

def test_purge_deletes_posts_past_the_window(session):
    make_profile(session, make_post(session, "old001", author="a", days_ago=200))
    make_profile(session, make_post(session, "new001", author="b", days_ago=10))
    session.commit()

    assert store.purge_old_posts(session, 180) == 1
    assert [p.reddit_id for p in session.scalars(select(Post)).all()] == ["new001"]
    # Derived rows go with it, or the summary outlives the post.
    assert count(session, Profile) == 1


def test_purge_is_inclusive_of_nothing_inside_the_window(session):
    make_post(session, "edge01", days_ago=179)
    session.commit()
    assert store.purge_old_posts(session, 180) == 0


def test_purge_is_disabled_by_zero_or_negative(session):
    make_post(session, "old002", days_ago=9999)
    session.commit()
    assert store.purge_old_posts(session, 0) == 0
    assert store.purge_old_posts(session, -1) == 0
    assert count(session, Post) == 1


def test_purge_on_an_empty_database(session):
    assert store.purge_old_posts(session, 180) == 0


def test_purged_posts_can_return_if_still_live(session):
    """Retention is not erasure: an old post that is still on Reddit and back
    inside the window is legitimately re-ingested. Only suppression is forever.
    """
    make_post(session, "old003", days_ago=200)
    session.commit()
    store.purge_old_posts(session, 180)
    assert store.upsert_posts(session, [scraped("old003", days_ago=1)]) == ["old003"]


# --- the CLI's permalink handling ----------------------------------------
# A removal request arrives as a link, not a base-36 id.

def test_post_id_from_permalink():
    from manage import post_id_from

    cases = {
        "1vfzt8u": "1vfzt8u",
        "https://www.reddit.com/r/makenewfriendsNL/comments/1vfzt8u/25m_looking/":
            "1vfzt8u",
        # No trailing slash, no slug.
        "https://reddit.com/r/Vriendenmaken/comments/abc123": "abc123",
        # Old-style and mobile hosts use the same path shape.
        "https://old.reddit.com/r/x/comments/zz9/title/": "zz9",
        "/r/x/comments/pp1/title/": "pp1",
    }
    for given, expected in cases.items():
        assert post_id_from(given) == expected, given


def test_post_id_from_rejects_a_link_with_no_id():
    import pytest as _pytest

    from manage import post_id_from

    for bad in ("https://reddit.com/r/somesub/", "https://example.com/x/y"):
        with _pytest.raises(ValueError, match="no post id"):
            post_id_from(bad)
