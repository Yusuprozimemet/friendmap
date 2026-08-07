"""Orchestration: scrape -> store -> extract -> geocode -> save, plus backfill."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app import alerts, config
from app.db import SessionLocal
from app.models import Post, Profile
from ingest import extractor, places, scraper, store


def _extract_and_save(session, posts: list[dict]) -> int:
    """Extract and commit batch by batch, so progress survives an interrupt."""
    if not posts:
        return 0
    saved = 0
    for batch in extractor.extract_batches(posts):
        if not batch:
            continue
        saved += store.save_profiles(session, batch, config.NVIDIA_MODEL)
        print(f"    saved {saved}/{len(posts)}")
    return saved


def run_daily(
    days: int = 7,
    check_deleted: int = 40,
    subreddits: list[str] | None = None,
) -> None:
    """The job a cron would call. `subreddits` overrides the configured set."""
    subs = subreddits or config.SUBREDDITS
    with SessionLocal() as session:
        store.seed_reference(session)

        sources = ", ".join(f"r/{s}" for s in subs)
        print(f"scraping {sources} (last {days} days)...")
        posts = scraper.fetch(days=days, subreddits=subs)
        print(f"  {len(posts)} posts in window (all sources)")

        new_ids = store.upsert_posts(session, posts)
        print(f"  {len(new_ids)} new")

        # Extract everything still missing a profile, not just today's new rows.
        # A batch that failed yesterday (timeout, rate limit) would otherwise
        # leave those posts invisible forever; this way the next run heals it.
        have = set(session.scalars(select(Profile.post_id)).all())
        todo = [p for p in posts if p["id"] not in have]
        if len(todo) > len(new_ids):
            print(f"  ({len(todo) - len(new_ids)} earlier post(s) still unextracted)")

        saved = _extract_and_save(session, todo)
        print(f"  {saved} profiles extracted")

        if check_deleted:
            stale = session.scalars(
                select(Post)
                .where(Post.deleted_at.is_(None))
                .order_by(Post.last_seen_at.asc())
                .limit(check_deleted)
            ).all()
            gone = [p.reddit_id for p in stale if not scraper.is_alive(p.url)]
            store.mark_deleted(session, gone)
            print(f"  checked {len(stale)} permalinks, {len(gone)} now deleted")

        # Retention before alerts, so a digest can never announce somebody the
        # same run is about to delete.
        purged = store.purge_old_posts(session, config.RETENTION_DAYS)
        if purged:
            print(f"  purged {purged} post(s) past {config.RETENTION_DAYS} days")

        # Alerts last: they should only ever consider people already stored.
        sent = alerts.run_alerts(session)
        if sent:
            print(f"  {sent} alert digest(s) sent")

    print("done.")


def regeocode() -> None:
    """Re-resolve stored location_raw against the current gazetteer.

    Free — adding a missing town or alias never needs another LLM call, because
    the model's raw location string was kept alongside the resolved place.
    """
    from ingest.store import _resolve_place

    with SessionLocal() as session:
        store.seed_reference(session)
        profiles = session.scalars(select(Profile)).all()
        changed = 0

        for profile in profiles:
            precision, city, province = places.lookup(profile.location_raw)
            place = _resolve_place(session, city, province)
            place_id = place.id if place else None
            if (profile.geo_precision, profile.place_id) != (precision, place_id):
                profile.geo_precision = precision
                profile.place_id = place_id
                changed += 1

        session.commit()
        print(f"{changed} of {len(profiles)} profiles re-geocoded")


def reextract(limit: int | None = None, before: datetime | None = None) -> None:
    """Re-run extraction over stored posts with the current prompt/model.

    The point of keeping raw post text separate from derived profiles: improving
    the prompt costs API calls, never a re-scrape.

    `before` skips posts already extracted at or after that moment, so an
    interrupted or partial re-run can be resumed without paying for the work
    twice — pass the time the prompt or vocabulary last changed. Posts with no
    profile at all are always included, whatever `before` says.
    """
    with SessionLocal() as session:
        # No upfront delete: save_profiles replaces per post, so a failed batch
        # leaves the previous extraction intact instead of emptying the app.
        stmt = select(Post).where(Post.deleted_at.is_(None)).order_by(Post.posted_at.desc())
        if before is not None:
            already_fresh = select(Profile.post_id).where(Profile.extracted_at >= before)
            stmt = stmt.where(Post.reddit_id.not_in(already_fresh))
        if limit:
            stmt = stmt.limit(limit)
        rows = session.scalars(stmt).all()

        posts = [{"id": p.reddit_id, "title": p.title, "body": p.body} for p in rows]
        print(f"re-extracting {len(posts)} posts...")
        saved = _extract_and_save(session, posts)
        print(f"{saved} profiles extracted")


def backfill(json_path: Path, limit: int | None = None) -> None:
    """Load an existing friends.json scrape and extract it."""
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    raw_posts = payload["posts"][:limit] if limit else payload["posts"]

    posts = [{
        "id": p["id"].removeprefix("rd:"),
        "subreddit": p.get("subreddit", "r/" + config.SUBREDDIT).removeprefix("r/"),
        "author": (p.get("author") or "").removeprefix("/u/"),
        "title": p["title"],
        "body": p.get("selftext", ""),
        "url": p["url"],
        "posted_at": datetime.fromisoformat(p["created_utc"]).astimezone(timezone.utc),
    } for p in raw_posts]

    with SessionLocal() as session:
        store.seed_reference(session)
        new_ids = store.upsert_posts(session, posts)
        print(f"{len(posts)} posts loaded, {len(new_ids)} new")

        # Extract anything without a profile, not just newly inserted rows, so
        # a half-finished backfill can be resumed by re-running.
        have = set(session.scalars(select(Profile.post_id)).all())
        todo = [p for p in posts if p["id"] not in have]
        print(f"{len(todo)} posts need extraction")

        saved = _extract_and_save(session, todo)
        print(f"{saved} profiles extracted")
