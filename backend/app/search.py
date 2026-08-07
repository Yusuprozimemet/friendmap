"""The one implementation of "which people match these filters".

Extracted from the profiles route so the alert job runs *exactly* the query
the user built in the UI. Two implementations would drift, and a saved search
that quietly stops meaning what it said when it was saved is worse than no
saved search at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import query as q
from app.models import Interest, Post, Profile, UserPerson
from app.schemas import PersonOut


def _csv(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


@dataclass
class SearchParams:
    """Mirrors the query string, so a saved search is just this serialised."""

    period: int | None = 30
    age_min: int = 18
    age_max: int = 70
    genders: str | None = None
    interests: str | None = None
    interest_mode: str = "any"
    langs: str | None = None
    provinces: str | None = None
    sources: str | None = None
    search: str | None = None
    state: str | None = None
    include_hidden: bool = False
    include_events: bool = False
    sort: str = "newest"

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "")}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchParams:
        """Build from loosely-typed input.

        Saved searches are stored as the query string the browser built, so
        every value arrives as a *string* — `period: "0"`, not `0`. Coercing
        here rather than at the call sites is what stops the nightly job from
        dying on `timedelta(days="0")`, and stops `"0"` (truthy!) from being
        read as a zero-day window that matches nobody.
        """
        known = set(cls.__dataclass_fields__)
        clean: dict[str, Any] = {}
        for key, value in (data or {}).items():
            if key not in known:
                continue
            if key in _INT_FIELDS:
                parsed = _as_int(value)
                # age_min/age_max have real defaults and no null meaning, so
                # unparseable input falls back rather than becoming None and
                # producing `BETWEEN NULL AND NULL`.
                if parsed is None and key != "period":
                    continue
                clean[key] = parsed
            elif key in _BOOL_FIELDS:
                clean[key] = _as_bool(value)
            else:
                clean[key] = None if value is None else str(value)
        return cls(**clean)


_INT_FIELDS = {"period", "age_min", "age_max"}
_BOOL_FIELDS = {"include_hidden", "include_events"}


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def run(
    session: Session,
    params: SearchParams,
    user_id: int | None = None,
) -> list[PersonOut]:
    """Filtered, deduped people, newest first."""
    stmt = q.base_query()

    if params.period:
        stmt = stmt.where(Post.posted_at >= q.cutoff_for(params.period))
    if not params.include_events:
        stmt = stmt.where(Profile.post_type == "profile")

    # Age filter keeps people who never stated an age — dropping them would
    # silently hide a fifth of the board behind a filter nobody touched.
    stmt = stmt.where(
        or_(Profile.age.is_(None), Profile.age.between(params.age_min, params.age_max))
    )

    if sources := [s.removeprefix("r/") for s in _csv(params.sources)]:
        stmt = stmt.where(Post.subreddit.in_(sources))
    if genders := _csv(params.genders):
        stmt = stmt.where(Profile.gender.in_(genders))
    if langs := _csv(params.langs):
        stmt = stmt.where(Profile.lang.in_(langs))

    if params.search:
        needle = f"%{params.search.strip()}%"
        stmt = stmt.where(
            or_(
                Post.title.ilike(needle),
                Post.body.ilike(needle),
                Profile.summary.ilike(needle),
                Profile.location_raw.ilike(needle),
            )
        )

    if wanted := _csv(params.interests):
        if params.interest_mode == "all":
            for slug in wanted:
                stmt = stmt.where(Profile.interests.any(Interest.slug == slug))
        else:
            stmt = stmt.where(Profile.interests.any(Interest.slug.in_(wanted)))

    profiles = session.scalars(stmt).unique().all()

    now = q.now_utc()
    repeats = q.repeat_counts(session)
    people = [q.to_person(p, now, repeats) for p in profiles]

    # Province filter needs the resolved place, so it lands after mapping.
    if provinces := set(_csv(params.provinces)):
        people = [p for p in people if p.province in provinces]

    people = q.dedupe_by_author(people)

    # Per-user state lands after dedupe: it keys on person_key, which is only
    # meaningful once one post per person has been chosen.
    if user_id is not None:
        rows = session.scalars(
            select(UserPerson).where(UserPerson.user_id == user_id)
        ).all()
        by_key = {r.person_key: r for r in rows}
        state = params.state

        if state == "saved":
            people = [p for p in people if (m := by_key.get(p.person_key)) and m.saved]
        elif state in ("contacted", "hidden"):
            people = [
                p for p in people
                if (m := by_key.get(p.person_key)) and m.status == state
            ]
        elif state == "none":
            people = [
                p for p in people
                if (m := by_key.get(p.person_key)) is None
                or (not m.saved and m.status is None)
            ]

        # Hidden people drop out everywhere except when explicitly asked for,
        # so map cluster counts match what the list says.
        if state != "hidden" and not params.include_hidden:
            people = [
                p for p in people
                if (m := by_key.get(p.person_key)) is None or m.status != "hidden"
            ]

    return people
