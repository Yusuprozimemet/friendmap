"""Insights + metadata. Deliberately global — not affected by Explore filters."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import query as q
from app.db import get_session
from app.models import Interest, Post, Profile, profile_interests
from app.schemas import HealthOut, InterestCount, LabelCount, StatsOut, WritingTipsOut

router = APIRouter(prefix="/api", tags=["stats"])

AGE_BUCKETS = [(18, 24), (25, 29), (30, 34), (35, 39), (40, 49), (50, 99)]
WEEKS = 16


@router.get("/stats", response_model=StatsOut)
def stats(session: Session = Depends(get_session)) -> StatsOut:
    now = q.now_utc()
    repeats = q.repeat_counts(session)
    profiles = session.scalars(
        q.base_query().where(Profile.post_type == "profile")
    ).unique().all()
    people = q.dedupe_by_author([q.to_person(p, now, repeats) for p in profiles])

    ages = sorted(p.age for p in people if p.age is not None)
    median_age = ages[len(ages) // 2] if ages else None

    posts_per_week = []
    for i in range(WEEKS):
        start = (WEEKS - 1 - i) * 7
        posts_per_week.append(
            sum(1 for p in people if start <= p.days_ago < start + 7)
        )

    city_counts = Counter(p.city for p in people if p.city)
    interest_counts = Counter(i for p in people for i in p.interests)

    age_buckets = [
        LabelCount(
            label=f"{lo}-{hi}",
            count=sum(1 for p in people if p.age is not None and lo <= p.age <= hi),
        )
        for lo, hi in AGE_BUCKETS
    ]

    return StatsOut(
        active_30d=sum(1 for p in people if p.days_ago <= 30),
        new_this_week=sum(1 for p in people if p.days_ago <= 7),
        cities_covered=len(city_counts),
        median_age=median_age,
        posts_per_week=posts_per_week,
        top_cities=[LabelCount(label=c, count=n) for c, n in city_counts.most_common(6)],
        interest_counts=[
            LabelCount(label=i, count=n) for i, n in interest_counts.most_common(6)
        ],
        age_buckets=age_buckets,
        newest_post_at=min(people, key=lambda p: p.days_ago).posted_at if people else None,
    )


@router.get("/meta/writing-tips", response_model=WritingTipsOut)
def writing_tips(session: Session = Depends(get_session)) -> WritingTipsOut:
    """Measured gaps in the real corpus, for the post composer.

    Every number here is computed from the live board. The app cannot say
    which posts *got replies* — Reddit's Atom feed carries no comment count
    and nothing stores one — so this deliberately reports what is missing
    rather than what "works". Advice the data cannot support isn't given.
    """
    rows = session.execute(
        select(Profile.age, Profile.geo_precision, Post.body)
        .join(Post, Profile.post_id == Post.reddit_id)
        .where(Post.deleted_at.is_(None), Profile.post_type == "profile")
    ).all()
    if not rows:
        return WritingTipsOut(sample_size=0, gaps=[], median_length=0, top_interests=[])

    interest_counts = session.execute(
        select(Interest.slug, func.count(profile_interests.c.profile_id))
        .select_from(Interest)
        .join(profile_interests, Interest.id == profile_interests.c.interest_id)
        .group_by(Interest.slug)
    ).all()

    # Must be counted over the same population as `rows` below. Counting
    # across every profile row — including event/meta types and profiles whose
    # post has since been deleted — inflated the tagged count against a
    # live-only denominator and understated the gap as 11% when it is 18%.
    live = (
        select(Profile.id)
        .join(Post, Profile.post_id == Post.reddit_id)
        .where(Post.deleted_at.is_(None), Profile.post_type == "profile")
    ).subquery()
    with_interests = session.scalar(
        select(func.count(func.distinct(profile_interests.c.profile_id)))
        .select_from(profile_interests)
        .join(live, live.c.id == profile_interests.c.profile_id)
    ) or 0

    total = len(rows)
    no_age = sum(1 for age, _, _ in rows if age is None)
    no_place = sum(1 for _, prec, _ in rows if prec in ("none", "country"))
    no_interests = max(0, total - with_interests)
    lengths = sorted(len(body or "") for _, _, body in rows)

    gaps = [
        LabelCount(label="location", count=no_place),
        LabelCount(label="interests", count=no_interests),
        LabelCount(label="age", count=no_age),
    ]
    return WritingTipsOut(
        sample_size=total,
        gaps=gaps,
        median_length=lengths[len(lengths) // 2],
        top_interests=[
            LabelCount(label=slug, count=n)
            for slug, n in sorted(interest_counts, key=lambda r: r[1], reverse=True)[:8]
        ],
    )


@router.get("/meta/sources", response_model=list[LabelCount])
def source_counts(session: Session = Depends(get_session)) -> list[LabelCount]:
    """Subreddits actually present in the data, biggest first.

    Read from the posts rather than from config, so a source that was ingested
    once and later removed from the env still labels its own rows.
    """
    rows = session.execute(
        select(Post.subreddit, func.count(Post.reddit_id))
        .where(Post.deleted_at.is_(None))
        .group_by(Post.subreddit)
    ).all()
    counts = [LabelCount(label=name, count=n) for name, n in rows if name]
    return sorted(counts, key=lambda c: c.count, reverse=True)


@router.get("/meta/interests", response_model=list[InterestCount])
def interest_counts(session: Session = Depends(get_session)) -> list[InterestCount]:
    """Global counts, so the filter chips don't renumber as you filter."""
    rows = session.execute(
        select(Interest.slug, func.count(profile_interests.c.profile_id))
        .select_from(Interest)
        .outerjoin(profile_interests, Interest.id == profile_interests.c.interest_id)
        .outerjoin(Profile, Profile.id == profile_interests.c.profile_id)
        .outerjoin(Post, Post.reddit_id == Profile.post_id)
        .where(Post.deleted_at.is_(None))
        .group_by(Interest.slug)
    ).all()
    counts = [InterestCount(slug=slug, count=count) for slug, count in rows if count]
    return sorted(counts, key=lambda c: c.count, reverse=True)


@router.get("/health", response_model=HealthOut)
def health(session: Session = Depends(get_session)) -> HealthOut:
    newest = session.scalar(
        select(func.max(Post.posted_at)).where(Post.deleted_at.is_(None))
    )
    return HealthOut(
        status="ok",
        posts=session.scalar(select(func.count(Post.reddit_id))) or 0,
        profiles=session.scalar(select(func.count(Profile.id))) or 0,
        newest_post_at=newest,
    )
