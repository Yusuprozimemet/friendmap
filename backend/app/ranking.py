"""Sort-by-overlap for people who've told us about themselves.

Deliberately a *sort*, never a filter: nobody disappears for scoring low. And
deliberately explainable — the same numbers that order the list also produce
the "3 shared interests · same city" line on the card, so the ranking can't
say one thing and show another.

This is not matchmaking and must not be presented as such. It is overlap
between two lists of self-declared facts.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models import UserProfile
from app.schemas import PersonOut
from app.theme_bucket import recency_weight

# Weights live together and are named, because they will be tuned — and per
# this project's convention, tuned from measurement rather than guessed.
W_INTERESTS = 3.0
W_PLACE = 2.0
W_AGE = 1.0
W_RECENCY = 0.5

#: Beyond this, more shared interests stop meaning much.
INTEREST_CAP = 3
#: Age score decays to zero over this many years outside the wanted range.
AGE_FALLOFF_YEARS = 10.0
#: What an unknown value scores.
#:
#: Two constraints, and the value has to sit between them:
#:
#: * Above a hard mismatch (0.0), so someone who didn't state their age isn't
#:   ranked below someone whose stated age you explicitly don't want.
#: * *Below* the weakest genuine signal — one shared interest scores 1/3, and
#:   same-province scores 1/2. At the original 0.5, saying nothing beat both:
#:   a profile with no interests outscored one sharing an interest with you,
#:   and "no location given" tied with "lives in your province". The top of
#:   every list filled up with people the app knows nothing about.
UNKNOWN = 0.25


@dataclass
class Explanation:
    score: float
    reasons: list[str]


def _interest_score(mine: set[str], theirs: set[str]) -> tuple[float, int]:
    if not mine or not theirs:
        return UNKNOWN, 0
    shared = len(mine & theirs)
    return min(shared, INTEREST_CAP) / INTEREST_CAP, shared


def _same(a: str | None, b: str | None) -> bool:
    """People type their own city; the gazetteer title-cases the map's.

    "voorschoten" and "Voorschoten" are the same place, and an exact match
    would silently score them as different — a wrong answer that looks like
    a working one.
    """
    return bool(a and b and a.strip().casefold() == b.strip().casefold())


def _place_score(profile: UserProfile, person: PersonOut) -> tuple[float, str | None]:
    if _same(profile.city, person.city):
        return 1.0, f"same city ({person.city})"
    if _same(profile.province, person.province):
        return 0.5, f"same province ({person.province})"
    if not profile.city and not profile.province:
        return UNKNOWN, None
    if person.city is None and person.province is None:
        return UNKNOWN, None
    return 0.0, None


def _age_score(profile: UserProfile, person: PersonOut) -> tuple[float, str | None]:
    if person.age is None:
        return UNKNOWN, None
    lo = profile.age_min
    hi = profile.age_max
    if lo is None and hi is None:
        return UNKNOWN, None
    lo = lo if lo is not None else 0
    hi = hi if hi is not None else 200
    if lo <= person.age <= hi:
        return 1.0, f"age {person.age} is in range"
    gap = lo - person.age if person.age < lo else person.age - hi
    return max(0.0, 1.0 - gap / AGE_FALLOFF_YEARS), None


def explain(profile: UserProfile, person: PersonOut) -> Explanation:
    mine = set(profile.interests or [])
    theirs = set(person.interests or [])

    interest, shared = _interest_score(mine, theirs)
    place, place_reason = _place_score(profile, person)
    age, age_reason = _age_score(profile, person)

    score = (
        W_INTERESTS * interest
        + W_PLACE * place
        + W_AGE * age
        + W_RECENCY * recency_weight(person.days_ago)
    )

    reasons: list[str] = []
    if shared:
        overlap = sorted(mine & theirs)[:3]
        reasons.append(
            f"{shared} shared interest{'s' if shared > 1 else ''}: {', '.join(overlap)}"
        )
    if place_reason:
        reasons.append(place_reason)
    if age_reason:
        reasons.append(age_reason)

    return Explanation(score=round(score, 4), reasons=reasons)


def sort_people(
    profile: UserProfile, people: list[PersonOut]
) -> list[PersonOut]:
    """Highest overlap first; ties fall back to newest so order is stable."""
    scored = [(explain(profile, p), p) for p in people]
    scored.sort(key=lambda pair: (pair[0].score, pair[1].posted_at), reverse=True)
    for ex, person in scored:
        person.match_score = ex.score
        person.match_reasons = ex.reasons
    return [person for _, person in scored]
