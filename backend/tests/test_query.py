"""Shared read logic: dedupe, mapping, and the map-position fallback."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import query as q
from app.schemas import PersonOut
from tests.conftest import make_place, make_post, make_profile

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


def person(id: str, author: str, *, days_ago: int = 1, hours_ago: int = 0) -> PersonOut:
    posted = NOW - timedelta(days=days_ago, hours=hours_ago)
    return PersonOut(
        id=id,
        author=author,
        subreddit="makenewfriendsNL",
        age=None,
        gender="unknown",
        city=None,
        province=None,
        precision="none",
        lat=None,
        lon=None,
        x=None,
        y=None,
        posted_at=posted,
        days_ago=days_ago,
        lang="en",
        title=id,
        body="",
        summary="",
        looking_for=None,
        interests=[],
        permalink="https://example.com",
        repeat_count=0,
        needs_review=False,
    )


# --- dedupe ---------------------------------------------------------------

def test_dedupe_keeps_one_entry_per_author():
    people = [person("old", "alice", days_ago=5), person("new", "alice", days_ago=1)]
    out = q.dedupe_by_author(people)
    assert [p.id for p in out] == ["new"]


def test_dedupe_uses_the_full_timestamp_not_whole_days():
    """Two posts on the same day tie on `days_ago`.

    They used to fall back to whatever order the database returned, which both
    picked an arbitrary post per author and left "Newest" not actually newest.
    """
    earlier = person("earlier", "alice", days_ago=0, hours_ago=9)
    later = person("later", "alice", days_ago=0, hours_ago=1)
    assert earlier.days_ago == later.days_ago
    assert [p.id for p in q.dedupe_by_author([earlier, later])] == ["later"]


def test_dedupe_spans_sources():
    """People cross-post the same appeal; that's one pin, not one per sub."""
    a = person("in_a", "alice", days_ago=2)
    b = person("in_b", "alice", days_ago=1)
    b.subreddit = "Vriendenmaken"
    assert len(q.dedupe_by_author([a, b])) == 1


def test_dedupe_keeps_every_post_from_deleted_accounts():
    """Empty author means "unknown person" — collapsing them would merge
    strangers into one."""
    people = [person("p1", "", days_ago=1), person("p2", "", days_ago=2)]
    assert len(q.dedupe_by_author(people)) == 2


def test_dedupe_returns_newest_first():
    people = [
        person("mid", "bob", days_ago=3),
        person("newest", "alice", days_ago=1),
        person("oldest", "carol", days_ago=9),
    ]
    assert [p.id for p in q.dedupe_by_author(people)] == ["newest", "mid", "oldest"]


def test_dedupe_handles_naive_timestamps():
    """SQLite (and any column read back without a tz) yields naive datetimes.

    Sorting a mix of naive and aware datetimes raises TypeError, so the sort
    key normalises — this is the regression test for that.
    """
    aware = person("aware", "alice", days_ago=1)
    naive = person("naive", "bob", days_ago=2)
    naive.posted_at = naive.posted_at.replace(tzinfo=None)
    assert [p.id for p in q.dedupe_by_author([naive, aware])] == ["aware", "naive"]


def test_dedupe_on_empty_input():
    assert q.dedupe_by_author([]) == []


# --- mapping --------------------------------------------------------------

def test_to_person_maps_a_placed_profile(session):
    place = make_place(session, "Zaandam", province="Noord-Holland",
                       lat=52.4389, lon=4.8267)
    post = make_post(session, "abc123", author="alice", title="Hallo")
    make_profile(session, post, place=place, geo_precision="city",
                 interests=("hiking", "coffee"))
    profile = session.scalars(q.base_query()).unique().one()

    out = q.to_person(profile, q.now_utc(), q.repeat_counts(session))
    assert out.id == "abc123"
    assert out.city == "Zaandam"
    assert out.province == "Noord-Holland"
    assert out.lat == 52.4389
    # Interests are sorted so the chips don't reorder between requests.
    assert out.interests == ["coffee", "hiking"]
    assert 0 < out.x < 100 and 0 < out.y < 100


def test_to_person_falls_back_to_amsterdam_for_unplaced_people(session):
    """Unplaced people still get map coordinates so they appear at all — but
    keep no city/province, so province filters and Insights stay truthful."""
    post = make_post(session, "nope01", author="bob")
    make_profile(session, post, place=None, geo_precision="none")
    profile = session.scalars(q.base_query()).unique().one()

    out = q.to_person(profile, q.now_utc(), q.repeat_counts(session))
    assert (out.x, out.y) == q.FALLBACK_XY
    assert out.city is None and out.province is None
    assert out.precision == "none"


def test_country_precision_does_not_borrow_the_place_coordinates(session):
    """"Nederland" resolves to no city — it must not land on a real pin."""
    place = make_place(session, "Utrecht", kind="province", province="Utrecht",
                       lat=52.1, lon=5.15)
    post = make_post(session, "ctry01")
    make_profile(session, post, place=place, geo_precision="country")
    profile = session.scalars(q.base_query()).unique().one()

    out = q.to_person(profile, q.now_utc(), {})
    assert (out.x, out.y) == q.FALLBACK_XY


def test_to_person_strips_the_feed_footer_at_read_time(session):
    """Also stripped at ingest; done here too so rows scraped before that
    landed are clean without a re-scrape."""
    post = make_post(session, "foot01", body="Real text.\n\nsubmitted by\n/u/alice")
    make_profile(session, post)
    profile = session.scalars(q.base_query()).unique().one()

    out = q.to_person(profile, q.now_utc(), q.repeat_counts(session))
    assert out.body == "Real text."
    assert "/u/alice" not in out.body


def test_to_person_never_serialises_the_author(session):
    """`author` is needed in-process for dedupe but must not reach the client."""
    post = make_post(session, "auth01", author="alice")
    make_profile(session, post)
    profile = session.scalars(q.base_query()).unique().one()

    out = q.to_person(profile, q.now_utc(), q.repeat_counts(session))
    assert out.author == "alice"
    assert "author" not in out.model_dump()


def test_repeat_count_excludes_the_current_post(session):
    """Shown as "also posted N× before", so their own post isn't a repeat."""
    for i in range(3):
        post = make_post(session, f"rep{i}", author="alice", days_ago=i + 1)
        make_profile(session, post)
    profiles = session.scalars(q.base_query()).unique().all()
    repeats = q.repeat_counts(session)

    people = [q.to_person(p, q.now_utc(), repeats) for p in profiles]
    assert {p.repeat_count for p in people} == {2}


def test_repeat_counts_ignores_deleted_posts_and_empty_authors(session):
    make_profile(session, make_post(session, "live01", author="alice"))
    make_profile(session, make_post(session, "gone01", author="alice", deleted=True))
    make_profile(session, make_post(session, "anon01", author=""))
    counts = q.repeat_counts(session)
    assert counts.get("alice") == 1
    assert "" not in counts


# --- base query -----------------------------------------------------------

def test_base_query_excludes_deleted_posts(session):
    make_profile(session, make_post(session, "live02", author="alice"))
    make_profile(session, make_post(session, "gone02", author="bob", deleted=True))
    ids = [p.post_id for p in session.scalars(q.base_query()).unique().all()]
    assert ids == ["live02"]


def test_base_query_excludes_meta_posts(session):
    """Moderator announcements are not people."""
    make_profile(session, make_post(session, "real01"), post_type="profile")
    make_profile(session, make_post(session, "mod001"), post_type="meta")
    ids = [p.post_id for p in session.scalars(q.base_query()).unique().all()]
    assert ids == ["real01"]


def test_cutoff_for():
    """None means all time — not "zero days ago", which matches nobody."""
    assert q.cutoff_for(None) is None
    cutoff = q.cutoff_for(7)
    assert cutoff is not None
    days = (q.now_utc() - cutoff).total_seconds() / 86400
    assert 6.99 < days < 7.01
