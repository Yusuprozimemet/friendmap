"""Match ranking.

The invariant worth protecting is the one written down in `app/ranking.py`:
**an unknown value must score above a hard mismatch but below the weakest real
signal.** At the original 0.5 it beat both, and the top of every list filled up
with people the app knew nothing about. That's a silent quality failure — the
feature still "works", it just recommends the emptiest profiles.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import ranking
from app.models import UserProfile
from app.schemas import PersonOut

NOW = datetime(2026, 8, 7, tzinfo=timezone.utc)


def person(
    *,
    id: str = "p1",
    age: int | None = 30,
    city: str | None = "Utrecht",
    province: str | None = "Utrecht",
    interests: tuple[str, ...] = ("hiking",),
    days_ago: int = 1,
) -> PersonOut:
    return PersonOut(
        id=id,
        subreddit="makenewfriendsNL",
        age=age,
        gender="F",
        city=city,
        province=province,
        precision="city" if city else "none",
        lat=None,
        lon=None,
        x=50.0,
        y=50.0,
        posted_at=NOW - timedelta(days=days_ago),
        days_ago=days_ago,
        lang="en",
        title="Hi",
        body="",
        summary="",
        looking_for=None,
        interests=list(interests),
        permalink="https://example.com",
        repeat_count=0,
        needs_review=False,
    )


def profile(
    *,
    city: str | None = "Utrecht",
    province: str | None = "Utrecht",
    interests: tuple[str, ...] = ("hiking", "coffee"),
    age_min: int | None = 25,
    age_max: int | None = 35,
) -> UserProfile:
    return UserProfile(
        user_id=1,
        age=30,
        city=city,
        province=province,
        interests=list(interests),
        age_min=age_min,
        age_max=age_max,
        updated_at=NOW,
    )


# --- the documented invariant --------------------------------------------

def test_unknown_scores_above_a_hard_mismatch():
    """Saying nothing must not rank below an explicit mismatch."""
    assert ranking.UNKNOWN > 0.0


def test_unknown_scores_below_one_shared_interest():
    """One shared interest is 1/3 of the interest component."""
    assert ranking.UNKNOWN < 1 / ranking.INTEREST_CAP


def test_unknown_scores_below_same_province():
    assert ranking.UNKNOWN < 0.5


def test_no_interests_ranks_below_one_shared_interest():
    """The end-to-end version of the invariant above."""
    me = profile()
    silent = ranking.explain(me, person(id="silent", interests=()))
    sharing = ranking.explain(me, person(id="sharing", interests=("hiking",)))
    assert sharing.score > silent.score


def test_no_location_ranks_below_same_province():
    me = profile(city=None, province="Utrecht")
    nowhere = ranking.explain(me, person(city=None, province=None))
    same_province = ranking.explain(me, person(city="Amersfoort", province="Utrecht"))
    assert same_province.score > nowhere.score


# --- components -----------------------------------------------------------

def test_same_city_beats_same_province_beats_elsewhere():
    me = profile(city="Utrecht", province="Utrecht")
    same_city = ranking.explain(me, person(city="Utrecht", province="Utrecht"))
    same_prov = ranking.explain(me, person(city="Amersfoort", province="Utrecht"))
    elsewhere = ranking.explain(me, person(city="Groningen", province="Groningen"))
    assert same_city.score > same_prov.score > elsewhere.score


def test_city_matching_ignores_case():
    """People type their own city; the gazetteer title-cases the map's."""
    me = profile(city="utrecht")
    ex = ranking.explain(me, person(city="Utrecht"))
    assert any("same city" in r for r in ex.reasons)


def test_city_matching_ignores_surrounding_whitespace():
    me = profile(city="  Utrecht ")
    assert any("same city" in r for r in ranking.explain(me, person(city="Utrecht")).reasons)


def test_shared_interests_are_capped():
    """Beyond the cap, more overlap stops changing the score."""
    me = profile(interests=("hiking", "coffee", "books", "gaming", "film"))
    three = ranking.explain(me, person(interests=("hiking", "coffee", "books")))
    five = ranking.explain(
        me, person(interests=("hiking", "coffee", "books", "gaming", "film"))
    )
    assert three.score == five.score


def test_age_in_range_scores_full_and_decays_outside():
    me = profile(age_min=25, age_max=35)
    inside = ranking.explain(me, person(age=30))
    just_out = ranking.explain(me, person(age=40))
    far_out = ranking.explain(me, person(age=60))
    assert inside.score > just_out.score > far_out.score


def test_age_decay_floors_at_zero_rather_than_going_negative():
    """A negative component would let a distant age drag a good match below
    someone with no overlap at all."""
    me = profile(age_min=25, age_max=35, interests=(), city=None, province=None)
    ex = ranking.explain(me, person(age=99, interests=(), city=None, province=None))
    assert ex.score >= 0.0


def test_unstated_age_is_unknown_not_a_mismatch():
    me = profile(age_min=25, age_max=35)
    unstated = ranking.explain(me, person(age=None))
    mismatch = ranking.explain(me, person(age=70))
    assert unstated.score > mismatch.score


def test_recency_contributes():
    me = profile()
    fresh = ranking.explain(me, person(days_ago=1))
    stale = ranking.explain(me, person(days_ago=90))
    assert fresh.score > stale.score


# --- reasons must match the score ----------------------------------------

def test_reasons_name_the_shared_interests():
    me = profile(interests=("hiking", "coffee"))
    ex = ranking.explain(me, person(interests=("hiking", "coffee")))
    assert any("2 shared interests" in r for r in ex.reasons)
    assert any("coffee" in r and "hiking" in r for r in ex.reasons)


def test_reason_is_singular_for_one_interest():
    ex = ranking.explain(profile(), person(interests=("hiking",)))
    assert any("1 shared interest:" in r for r in ex.reasons)


def test_no_reasons_claimed_when_nothing_overlaps():
    """The card shows these reasons verbatim — an empty overlap must not
    produce a line implying one."""
    me = profile(interests=("gaming",), city="Groningen", province="Groningen")
    ex = ranking.explain(me, person(interests=("hiking",), city="Maastricht",
                                    province="Limburg", age=70))
    assert ex.reasons == []


# --- sorting --------------------------------------------------------------

def test_sort_people_orders_by_score_and_annotates():
    me = profile(interests=("hiking",), city="Utrecht", province="Utrecht")
    weak = person(id="weak", interests=(), city="Maastricht", province="Limburg", age=70)
    strong = person(id="strong", interests=("hiking",), city="Utrecht", province="Utrecht")
    ordered = ranking.sort_people(me, [weak, strong])
    assert [p.id for p in ordered] == ["strong", "weak"]
    # The numbers shown on the card are the numbers that did the sorting.
    assert ordered[0].match_score is not None
    assert ordered[0].match_score > ordered[1].match_score
    assert any("same city" in r for r in ordered[0].match_reasons)


def test_sort_people_is_a_sort_and_never_a_filter():
    """Nobody disappears for scoring low."""
    me = profile()
    people = [person(id=f"p{i}", interests=()) for i in range(5)]
    assert len(ranking.sort_people(me, people)) == 5


def test_ties_fall_back_to_newest():
    me = profile()
    older = person(id="older", days_ago=3)
    newer = person(id="newer", days_ago=2)
    ordered = ranking.sort_people(me, [older, newer])
    assert ordered[0].match_score == ordered[1].match_score
    assert [p.id for p in ordered] == ["newer", "older"]


def test_empty_list_is_fine():
    assert ranking.sort_people(profile(), []) == []


def test_score_is_rounded_for_display():
    ex = ranking.explain(profile(), person())
    assert ex.score == pytest.approx(round(ex.score, 4))
