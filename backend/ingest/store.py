"""Database writes for the ingest side."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity import person_key
from app.models import (
    INTEREST_VOCAB,
    Interest,
    Place,
    Post,
    Profile,
    Suppression,
)
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


def suppressed_targets(session: Session) -> tuple[set[str], set[str]]:
    """(post ids, person keys) that must never be stored again."""
    rows = session.execute(
        select(Suppression.reddit_id, Suppression.person_key)
    ).all()
    ids = {r[0] for r in rows if r[0]}
    keys = {r[1] for r in rows if r[1]}
    return ids, keys


def upsert_posts(session: Session, posts: list[dict]) -> list[str]:
    """Insert unseen posts, refresh last_seen_at on known ones.

    Returns the ids of posts that are new (i.e. still need extraction).
    """
    now = datetime.now(timezone.utc)

    # Erasure is enforced here rather than at read time, because the scrape is
    # what would otherwise undo it: the post is still live on Reddit, so
    # deleting the row only removes it until tomorrow morning.
    dropped_ids, dropped_keys = suppressed_targets(session)
    if dropped_ids or dropped_keys:
        before = len(posts)
        posts = [
            p for p in posts
            if p["id"] not in dropped_ids
            and person_key(p.get("author") or "") not in dropped_keys
        ]
        if len(posts) < before:
            print(f"  {before - len(posts)} suppressed post(s) skipped")

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


def suppress(
    session: Session,
    *,
    reddit_id: str | None = None,
    author: str | None = None,
    reason: str = "",
) -> tuple[int, int]:
    """Honour an erasure request: delete now, and record so it stays deleted.

    Returns (posts deleted, suppression rows added). Give a `reddit_id` to
    remove one post, or an `author` to remove a person entirely — including
    posts they have not written yet, which is what "take me off this site"
    means. The author is converted to its keyed HMAC immediately and the
    username is never stored.

    Deleting the rows without recording the suppression would be undone by the
    next scrape, because the post is still live on Reddit.
    """
    if not reddit_id and not author:
        raise ValueError("suppress needs either reddit_id or author")

    key = person_key(author) if author else None
    if author and not key:
        raise ValueError(
            "cannot suppress by author without PERSON_KEY_SECRET set — the key "
            "would not match the one the scrape computes"
        )

    now = datetime.now(timezone.utc)
    added = 0
    exists = session.scalar(
        select(Suppression).where(
            Suppression.reddit_id.is_(reddit_id), Suppression.person_key.is_(key)
        )
    )
    if exists is None:
        session.add(
            Suppression(
                reddit_id=reddit_id, person_key=key, reason=reason, created_at=now
            )
        )
        added = 1

    # Remove what is already stored. Profiles cascade from posts.
    stmt = select(Post)
    if reddit_id:
        stmt = stmt.where(Post.reddit_id == reddit_id)
    else:
        # The author column is still present locally; match on it directly
        # rather than recomputing keys for every row.
        stmt = stmt.where(Post.author == (author or "").strip())
    doomed = session.scalars(stmt).all()
    for post in doomed:
        session.delete(post)

    session.commit()
    return len(doomed), added


def purge_old_posts(session: Session, older_than_days: int) -> int:
    """Delete posts past the retention window. Returns how many went.

    Art. 5(1)(e): the UI hiding posts after 30 days is not the same as not
    keeping them. Profiles and interest links cascade from the post, so this is
    one delete per row rather than a manual sweep of every derived table.
    """
    if older_than_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    doomed = session.scalars(select(Post).where(Post.posted_at < cutoff)).all()
    for post in doomed:
        session.delete(post)
    session.commit()
    return len(doomed)
