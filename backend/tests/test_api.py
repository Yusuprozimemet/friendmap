"""The HTTP surface, driven in-process through TestClient.

These are the contract the frontend codes against, plus the two headers that
carry a policy decision (no indexing, rate limiting).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app import alerts
from app.models import SavedSearch
from tests.conftest import make_place, make_post, make_profile, make_user


def test_healthz_does_not_touch_the_database(client):
    """Render restarts a service whose health check fails, so tying liveness to
    Postgres would turn a brief DB blip into a restart loop."""
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.text == "ok"


def test_health_reports_counts(client, session):
    make_profile(session, make_post(session, "h00001"))
    make_profile(session, make_post(session, "h00002"))
    session.commit()

    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["posts"] == 2
    assert body["profiles"] == 2
    assert body["newest_post_at"] is not None


def test_health_on_an_empty_database(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "posts": 0, "profiles": 0, "newest_post_at": None}


def test_robots_disallows_everything(client):
    """The posts are already public; the aggregation is what shouldn't be
    searchable."""
    assert "Disallow: /" in client.get("/robots.txt").text


def test_every_response_carries_the_noindex_header(client):
    for path in ("/healthz", "/api/health", "/robots.txt"):
        assert "noindex" in client.get(path).headers["x-robots-tag"]


def test_api_responses_carry_rate_limit_headers(client):
    r = client.get("/api/health")
    assert "x-ratelimit-limit" in r.headers
    assert int(r.headers["x-ratelimit-remaining"]) >= 0


# --- profiles -------------------------------------------------------------

def test_list_profiles_shape(client, session):
    place = make_place(session, "Utrecht", province="Utrecht", lat=52.0907, lon=5.1214)
    post = make_post(session, "p00001", author="alice", title="Hoi")
    make_profile(session, post, place=place, age=28, interests=("hiking",))
    session.commit()

    body = client.get("/api/profiles").json()
    assert body["total"] == 1
    assert body["placed"] == 1
    assert body["unplaced"] == 0

    person = body["people"][0]
    assert person["id"] == "p00001"
    assert person["city"] == "Utrecht"
    assert person["age"] == 28
    assert person["interests"] == ["hiking"]
    # The username is never serialised, and person_key stands in for it.
    assert "author" not in person
    assert person["person_key"]


def test_list_profiles_excludes_events_by_default(client, session):
    make_profile(session, make_post(session, "prof01"), post_type="profile")
    make_profile(session, make_post(session, "evnt01", author="bob"), post_type="event")
    session.commit()

    default = client.get("/api/profiles").json()
    assert [p["id"] for p in default["people"]] == ["prof01"]

    with_events = client.get("/api/profiles?include_events=true").json()
    assert {p["id"] for p in with_events["people"]} == {"prof01", "evnt01"}


def test_age_filter_keeps_people_who_never_stated_an_age(client, session):
    """Dropping them would silently hide a fifth of the board behind a filter
    nobody touched."""
    make_profile(session, make_post(session, "aged01", author="alice"), age=30)
    make_profile(session, make_post(session, "noage1", author="bob"), age=None)
    make_profile(session, make_post(session, "aged02", author="carol"), age=65)
    session.commit()

    body = client.get("/api/profiles?age_min=25&age_max=35").json()
    assert {p["id"] for p in body["people"]} == {"aged01", "noage1"}


def test_period_filter(client, session):
    make_profile(session, make_post(session, "fresh1", author="alice", days_ago=2))
    make_profile(session, make_post(session, "stale1", author="bob", days_ago=200))
    session.commit()

    assert {p["id"] for p in client.get("/api/profiles?period=30").json()["people"]} == {
        "fresh1"
    }
    # 0 means all time, not a zero-day window.
    assert len(client.get("/api/profiles?period=0").json()["people"]) == 2


def test_source_filter_accepts_names_with_and_without_the_prefix(client, session):
    make_profile(session, make_post(session, "src001", author="alice",
                                    subreddit="makenewfriendsNL"))
    make_profile(session, make_post(session, "src002", author="bob",
                                    subreddit="Vriendenmaken"))
    session.commit()

    for query in ("sources=Vriendenmaken", "sources=r/Vriendenmaken"):
        body = client.get(f"/api/profiles?{query}").json()
        assert [p["id"] for p in body["people"]] == ["src002"]


def test_interest_filter_any_versus_all(client, session):
    make_profile(session, make_post(session, "both01", author="alice"),
                 interests=("hiking", "coffee"))
    make_profile(session, make_post(session, "one001", author="bob"),
                 interests=("hiking",))
    session.commit()

    any_mode = client.get("/api/profiles?interests=hiking,coffee").json()
    assert {p["id"] for p in any_mode["people"]} == {"both01", "one001"}

    all_mode = client.get(
        "/api/profiles?interests=hiking,coffee&interest_mode=all"
    ).json()
    assert [p["id"] for p in all_mode["people"]] == ["both01"]


def test_text_search_covers_title_body_and_summary(client, session):
    make_profile(session, make_post(session, "txt001", author="alice",
                                    title="Bouldering buddy?"), summary="")
    make_profile(session, make_post(session, "txt002", author="bob",
                                    title="Hi", body="I do bouldering weekly"),
                 summary="")
    make_profile(session, make_post(session, "txt003", author="carol", title="Hi",
                                    body="Board games"), summary="Loves bouldering")
    make_profile(session, make_post(session, "txt004", author="dave", title="Hi",
                                    body="Knitting"), summary="Knits")
    session.commit()

    body = client.get("/api/profiles?search=bouldering").json()
    assert {p["id"] for p in body["people"]} == {"txt001", "txt002", "txt003"}


def test_province_filter(client, session):
    utrecht = make_place(session, "Utrecht", province="Utrecht", lat=52.09, lon=5.12)
    limburg = make_place(session, "Maastricht", province="Limburg", lat=50.85, lon=5.69)
    make_profile(session, make_post(session, "prv001", author="alice"), place=utrecht)
    make_profile(session, make_post(session, "prv002", author="bob"), place=limburg)
    session.commit()

    body = client.get("/api/profiles?provinces=Limburg").json()
    assert [p["id"] for p in body["people"]] == ["prv002"]


def test_deleted_posts_are_not_served(client, session):
    make_profile(session, make_post(session, "gone01", author="alice", deleted=True))
    session.commit()
    assert client.get("/api/profiles").json()["total"] == 0


def test_get_one_profile(client, session):
    make_profile(session, make_post(session, "one001", title="Hallo"))
    session.commit()

    r = client.get("/api/profiles/one001")
    assert r.status_code == 200
    assert r.json()["title"] == "Hallo"


def test_get_a_missing_profile_is_404(client):
    assert client.get("/api/profiles/nosuch").status_code == 404


def test_invalid_query_params_are_rejected(client):
    """FastAPI's validation, asserted so a loosened pattern is noticed."""
    assert client.get("/api/profiles?sort=random").status_code == 422
    assert client.get("/api/profiles?interest_mode=some").status_code == 422
    assert client.get("/api/profiles?age_min=999").status_code == 422


# --- stats ----------------------------------------------------------------

def test_stats_on_an_empty_database(client):
    """The dashboard renders before the first ingest, so this must not 500."""
    body = client.get("/api/stats").json()
    assert body["active_30d"] == 0
    assert body["median_age"] is None
    assert body["newest_post_at"] is None
    assert len(body["posts_per_week"]) == 16


def test_stats_counts_people_not_posts(client, session):
    """Someone who posted three times is one person in the numbers."""
    for i in range(3):
        make_profile(session, make_post(session, f"rep{i:03}", author="alice",
                                        days_ago=i + 1))
    make_profile(session, make_post(session, "solo01", author="bob", days_ago=1))
    session.commit()

    body = client.get("/api/stats").json()
    assert body["active_30d"] == 2
    assert body["new_this_week"] == 2


def test_stats_reports_cities_and_median_age(client, session):
    utrecht = make_place(session, "Utrecht", province="Utrecht", lat=52.09, lon=5.12)
    make_profile(session, make_post(session, "st0001", author="alice"),
                 place=utrecht, age=20)
    make_profile(session, make_post(session, "st0002", author="bob"),
                 place=utrecht, age=40)
    make_profile(session, make_post(session, "st0003", author="carol"), age=30)
    session.commit()

    body = client.get("/api/stats").json()
    assert body["cities_covered"] == 1
    assert body["median_age"] == 30
    assert body["top_cities"] == [{"label": "Utrecht", "count": 2}]


def test_meta_sources_is_read_from_the_data(client, session):
    """A source removed from config still labels its own rows."""
    for i in range(2):
        make_profile(session, make_post(session, f"nl{i:04}", author=f"a{i}",
                                        subreddit="makenewfriendsNL"))
    make_profile(session, make_post(session, "vm0001", author="b0",
                                    subreddit="retired_sub"))
    session.commit()

    body = client.get("/api/meta/sources").json()
    assert body == [
        {"label": "makenewfriendsNL", "count": 2},
        {"label": "retired_sub", "count": 1},
    ]


def test_meta_interests_omits_unused_tags(client, session):
    make_profile(session, make_post(session, "int001"), interests=("hiking",))
    session.commit()

    body = client.get("/api/meta/interests").json()
    assert body == [{"slug": "hiking", "count": 1}]


def test_writing_tips_on_an_empty_database(client):
    body = client.get("/api/meta/writing-tips").json()
    assert body["sample_size"] == 0
    assert body["median_length"] == 0


def test_writing_tips_measures_gaps(client, session):
    make_profile(session, make_post(session, "wt0001", author="alice", body="x" * 100),
                 age=None, geo_precision="none", interests=())
    make_profile(session, make_post(session, "wt0002", author="bob", body="y" * 200),
                 age=30, geo_precision="city", interests=("hiking",))
    session.commit()

    body = client.get("/api/meta/writing-tips").json()
    assert body["sample_size"] == 2
    gaps = {g["label"]: g["count"] for g in body["gaps"]}
    assert gaps == {"location": 1, "interests": 1, "age": 1}


# --- unsubscribe ----------------------------------------------------------

def test_unsubscribe_switches_the_search_off(client, session):
    user = make_user(session)
    row = SavedSearch(
        user_id=user.id,
        name="Climbers",
        filters={},
        cadence="daily",
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.commit()

    token = alerts.unsubscribe_token(row.id)
    r = client.get(f"/api/alerts/unsubscribe?token={token}")
    assert r.status_code == 200
    assert "Climbers" in r.text
    session.refresh(row)
    assert row.cadence == "off"


def test_unsubscribe_rejects_an_invalid_token(client):
    r = client.get("/api/alerts/unsubscribe?token=forged")
    assert r.status_code == 400


def test_unsubscribe_for_a_deleted_search_is_not_an_error(client, session):
    """The link outlives the search it names; a 500 in an email client is worse
    than a plain reassurance."""
    token = alerts.unsubscribe_token(99999)
    r = client.get(f"/api/alerts/unsubscribe?token={token}")
    assert r.status_code == 200
    assert "no longer exists" in r.text


# --- auth is off in tests -------------------------------------------------

def test_auth_config_reports_disabled(client):
    """With no Google credentials the UI hides the button rather than offering
    a sign-in that cannot work."""
    body = client.get("/api/auth/config").json()
    assert body["enabled"] is False


def test_signed_in_only_routes_are_closed(client):
    for path in ("/api/me/people", "/api/me/profile", "/api/me/searches"):
        assert client.get(path).status_code in (401, 403)
