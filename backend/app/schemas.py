"""Response shapes. The frontend consumes these directly — no client-side
geometry or date math beyond formatting.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PersonOut(BaseModel):
    id: str                      # reddit post id
    # Needed in-process for dedupe and repeat counts, never serialised: the
    # API has no reason to hand out usernames, and the permalink already
    # takes anyone who wants one to the post itself.
    author: str = Field(default="", exclude=True)
    # Stable across reposts, unlike `id` which is a post id. "" when the
    # person can't be keyed (deleted account, or no PERSON_KEY_SECRET set).
    person_key: str = ""
    subreddit: str               # which source this came from, without "r/"
    age: int | None
    gender: str
    city: str | None
    province: str | None
    precision: str               # city | province | country | none
    lat: float | None
    lon: float | None
    x: float | None              # % across the design's NL svg
    y: float | None              # % down the design's NL svg
    posted_at: datetime
    days_ago: int
    lang: str
    title: str
    body: str
    summary: str
    looking_for: str | None
    interests: list[str]
    permalink: str
    repeat_count: int
    needs_review: bool
    # Populated only when sort=match; see app/ranking.py.
    match_score: float | None = None
    match_reasons: list[str] = []


class UserOut(BaseModel):
    """What the browser is told about the signed-in account. Nothing more."""

    id: int
    email: str
    name: str
    picture: str


class PersonStateOut(BaseModel):
    person_key: str
    saved: bool
    status: str | None           # null | contacted | hidden
    note: str
    updated_at: datetime


class PersonStateIn(BaseModel):
    """Partial update. Unset fields keep their stored value."""

    saved: bool | None = None
    status: str | None = None
    #: `status` is nullable *and* clearing it is meaningful, so "was it sent?"
    #: can't be inferred from None alone.
    set_status: bool = False
    note: str | None = None


class UserProfileOut(BaseModel):
    """The viewer's own self-description, used only for match ranking."""

    age: int | None
    city: str | None
    province: str | None
    interests: list[str]
    age_min: int | None
    age_max: int | None


class UserProfileIn(BaseModel):
    age: int | None = None
    city: str | None = None
    province: str | None = None
    interests: list[str] = []
    age_min: int | None = None
    age_max: int | None = None


class SavedSearchOut(BaseModel):
    id: int
    name: str
    filters: dict
    cadence: str
    last_run_at: datetime | None
    last_match_at: datetime | None
    new_matches: int = 0


class SavedSearchIn(BaseModel):
    name: str
    filters: dict
    cadence: str = "weekly"


class SavedSearchPatch(BaseModel):
    name: str | None = None
    cadence: str | None = None


class ProfileListOut(BaseModel):
    total: int
    placed: int
    unplaced: int
    people: list[PersonOut]


class InterestCount(BaseModel):
    slug: str
    count: int


class LabelCount(BaseModel):
    label: str
    count: int


class WritingTipsOut(BaseModel):
    """Measured gaps in the corpus, for the post composer.

    Note what is absent: any claim about which posts got replies. The feed
    carries no comment count, so that would be invention.
    """

    sample_size: int
    gaps: list[LabelCount]          # label -> how many posts lack it
    median_length: int              # characters
    top_interests: list[LabelCount]


class StatsOut(BaseModel):
    active_30d: int
    new_this_week: int
    cities_covered: int
    median_age: int | None
    posts_per_week: list[int]        # oldest -> newest, 16 buckets
    top_cities: list[LabelCount]
    interest_counts: list[LabelCount]
    age_buckets: list[LabelCount]
    newest_post_at: datetime | None


class HealthOut(BaseModel):
    status: str
    posts: int
    profiles: int
    newest_post_at: datetime | None
