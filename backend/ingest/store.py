"""Database writes for the ingest side."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import INTEREST_VOCAB, Interest, Place, Post, Profile
from ingest import places as gazetteer
from ingest.extractor import Extracted


def seed_reference(session: Session) -> tuple[int, int]:
    """Idempotently load the gazetteer and interest vocabulary."""
    existing_places = {
        (p.name, p.kind) for p in session.scalars(select(Place)).all()
    }
    added_places = 0
    for row in gazetteer.all_places():
        if (row["name"], row["kind"]) not in existing_places:
            session.add(Place(**row))
            added_places += 1

    existing_interests = {i.slug for i in session.scalars(select(Interest)).all()}
    added_interests = 0
    for slug in INTEREST_VOCAB:
        if slug not in existing_interests:
            session.add(Interest(slug=slug))
            added_interests += 1

    session.commit()
    return added_places, added_interests


def upsert_posts(session: Session, posts: list[dict]) -> list[str]:
    """Insert unseen posts, refresh last_seen_at on known ones.

    Returns the ids of posts that are new (i.e. still need extraction).
    """
    now = datetime.now(timezone.utc)
    ids = [p["id"] for p in posts]
    known = set(
        session.scalars(select(Post.reddit_id).where(Post.reddit_id.in_(ids))).all()
    ) if ids else set()

    new_ids = []
    for post in posts:
        if post["id"] in known:
            session.execute(
                Post.__table__.update()
                .where(Post.reddit_id == post["id"])
                .values(last_seen_at=now, deleted_at=None)
            )
            continue
        session.add(Post(
            reddit_id=post["id"],
            subreddit=post["subreddit"],
            author=post["author"],
            title=post["title"],
            body=post["body"],
            url=post["url"],
            posted_at=post["posted_at"],
            scraped_at=now,
            last_seen_at=now,
        ))
        new_ids.append(post["id"])

    session.commit()
    return new_ids


def _resolve_place(session: Session, city: str | None, province: str | None) -> Place | None:
    if city:
        place = session.scalar(
            select(Place).where(Place.name == city, Place.kind == "city")
        )
        if place:
            return place
    if province:
        return session.scalar(
            select(Place).where(Place.name == province, Place.kind == "province")
        )
    return None


def save_profiles(
    session: Session, extracted: dict[str, Extracted], model: str
) -> int:
    """Write extracted profiles, replacing any existing one for the same post."""
    interests_by_slug = {
        i.slug: i for i in session.scalars(select(Interest)).all()
    }
    now = datetime.now(timezone.utc)
    saved = 0

    for post_id, item in extracted.items():
        precision, city, province = gazetteer.lookup(item.location_raw)
        place = _resolve_place(session, city, province)

        existing = session.scalar(select(Profile).where(Profile.post_id == post_id))
        if existing is not None:
            session.delete(existing)
            session.flush()

        profile = Profile(
            post_id=post_id,
            age=item.age,
            gender=item.gender,
            location_raw=item.location_raw,
            place_id=place.id if place else None,
            geo_precision=precision,
            post_type=item.post_type,
            lang=item.lang,
            looking_for=item.looking_for,
            summary=item.summary,
            confidence=item.confidence,
            needs_review=item.needs_review,
            model=model,
            extracted_at=now,
        )
        profile.interests = [
            interests_by_slug[s] for s in item.interests if s in interests_by_slug
        ]
        session.add(profile)
        saved += 1

    session.commit()
    return saved


def mark_deleted(session: Session, post_ids: list[str]) -> None:
    if not post_ids:
        return
    session.execute(
        Post.__table__.update()
        .where(Post.reddit_id.in_(post_ids))
        .values(deleted_at=datetime.now(timezone.utc))
    )
    session.commit()
