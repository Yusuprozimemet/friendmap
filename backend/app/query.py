"""Shared read logic for the API routes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.identity import person_key
from app.models import Post, Profile
from app.schemas import PersonOut
from ingest.places import CITIES
from ingest.projection import to_percent
from ingest.textclean import strip_feed_footer

# People who never named a place are pinned to Amsterdam so they show up on the
# map rather than hiding in a tray. They keep precision "none"/"country" and get
# no city/province, so province filters and the Insights city ranking stay
# truthful — only their map position is borrowed.
_FALLBACK_LAT, _FALLBACK_LON, _ = CITIES["Amsterdam"]
FALLBACK_XY = to_percent(_FALLBACK_LAT, _FALLBACK_LON)


def _days_ago(posted_at: datetime, now: datetime) -> int:
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    return max(0, (now - posted_at).days)


def base_query():
    """Live, non-meta profiles with their post joined."""
    return (
        select(Profile)
        .join(Post, Profile.post_id == Post.reddit_id)
        .options(joinedload(Profile.post), joinedload(Profile.place))
        .where(Post.deleted_at.is_(None), Profile.post_type != "meta")
    )


def repeat_counts(session: Session) -> dict[str, int]:
    """author -> number of posts they've made (used for 'also posted N× before')."""
    rows = session.execute(
        select(Post.author, func.count(Post.reddit_id))
        .where(Post.deleted_at.is_(None), Post.author != "")
        .group_by(Post.author)
    ).all()
    return dict(rows)


def to_person(profile: Profile, now: datetime, repeats: dict[str, int]) -> PersonOut:
    post = profile.post
    place = profile.place

    city = place.name if place and place.kind == "city" else None
    province = place.province if place else None

    if place is not None and profile.geo_precision in ("city", "province"):
        x, y = to_percent(place.lat, place.lon)
    else:
        x, y = FALLBACK_XY

    author = post.author or ""
    return PersonOut(
        id=post.reddit_id,
        author=author,
        person_key=person_key(author),
        subreddit=post.subreddit,
        age=profile.age,
        gender=profile.gender,
        city=city,
        province=province,
        precision=profile.geo_precision,
        lat=place.lat if place else None,
        lon=place.lon if place else None,
        x=x,
        y=y,
        posted_at=post.posted_at,
        days_ago=_days_ago(post.posted_at, now),
        lang=profile.lang,
        title=post.title,
        # Also stripped at ingest; done here too so rows scraped before that
        # landed are clean without a re-scrape or a migration.
        body=strip_feed_footer(post.body),
        summary=profile.summary,
        looking_for=profile.looking_for,
        interests=sorted(i.slug for i in profile.interests),
        permalink=post.url,
        repeat_count=max(0, repeats.get(author, 1) - 1) if author else 0,
        needs_review=profile.needs_review,
    )


def _sort_key(person: PersonOut) -> datetime:
    """Timezone-aware posting time, for a total order across mixed rows."""
    posted = person.posted_at
    return posted if posted.tzinfo else posted.replace(tzinfo=timezone.utc)


def dedupe_by_author(people: list[PersonOut]) -> list[PersonOut]:
    """One entry per person — their most recent post wins.

    Spans sources: plenty of people post the same appeal to every NL friend
    subreddit, and they should be one pin on the map, not one per subreddit.

    Done in Python rather than SQL because the result set here is small
    (hundreds, not millions) and a window function would make the filter
    composition considerably harder to follow.
    """
    seen: set[str] = set()
    out: list[PersonOut] = []
    # Sort on the full timestamp, not days_ago. days_ago is whole days, so
    # everyone who posted today tied at 0 and fell back to whatever order the
    # database returned — which both picked an arbitrary post per author and
    # left the "Newest" list not actually newest-first.
    for person in sorted(people, key=_sort_key, reverse=True):
        if person.author:
            if person.author in seen:
                continue
            seen.add(person.author)
        out.append(person)
    return out


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def cutoff_for(days: int | None) -> datetime | None:
    return None if days is None else now_utc() - timedelta(days=days)
