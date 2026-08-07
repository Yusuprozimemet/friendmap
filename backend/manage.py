"""CLI for the local app.

    python manage.py init-db                 create tables + seed gazetteer
    python manage.py backfill ../../friends.json [--limit N]
    python manage.py ingest [--days 7]       the daily job
    python manage.py serve                   run the API on :8000
    python manage.py reset --yes             drop every table (destructive)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Imported after the sys.path insert above, which is what makes them importable.
from app.db import SessionLocal, engine
from app.models import Base


def cmd_init_db(_args) -> None:
    from ingest.store import seed_reference

    Base.metadata.create_all(engine)
    print("tables created")
    with SessionLocal() as session:
        places, interests = seed_reference(session)
    print(f"seeded {places} places, {interests} interests")


def cmd_backfill(args) -> None:
    from ingest.pipeline import backfill

    path = Path(args.path).resolve()
    if not path.exists():
        raise SystemExit(f"no such file: {path}")
    backfill(path, limit=args.limit)


def cmd_regeocode(_args) -> None:
    from ingest.pipeline import regeocode

    regeocode()


def cmd_reextract(args) -> None:
    from datetime import datetime, timezone

    from ingest.pipeline import reextract

    before = None
    if args.before:
        before = datetime.fromisoformat(args.before)
        if before.tzinfo is None:
            before = before.replace(tzinfo=timezone.utc)
    reextract(limit=args.limit, before=before)


def cmd_ingest(args) -> None:
    from ingest.pipeline import run_daily

    subs = (
        [s.strip().removeprefix("r/") for s in args.sources.split(",") if s.strip()]
        if args.sources
        else None
    )
    run_daily(days=args.days, check_deleted=args.check_deleted, subreddits=subs)


def post_id_from(value: str) -> str:
    """Accept either a bare reddit id or a full permalink.

    A removal request arrives as a link, not an id — nobody reading their own
    post knows what a base-36 fullname is. Reddit permalinks are
    /r/<sub>/comments/<id>/<slug>/, so the segment after "comments" is the id.
    """
    if "/" not in value:
        return value
    parts = [p for p in value.split("/") if p]
    try:
        return parts[parts.index("comments") + 1]
    except (ValueError, IndexError):
        raise ValueError(f"no post id found in {value!r}") from None


def cmd_suppress(args) -> None:
    """Honour an erasure request so the next scrape cannot undo it."""
    from ingest.store import suppress

    if not args.post and not args.author:
        raise SystemExit("give --post <reddit_id|url> or --author <username>")

    try:
        post_id = post_id_from(args.post) if args.post else None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    with SessionLocal() as session:
        deleted, added = suppress(
            session, reddit_id=post_id, author=args.author, reason=args.reason
        )
    target = f"post {post_id}" if post_id else f"author {args.author!r}"
    print(f"{target}: {deleted} row(s) deleted, {added} suppression(s) recorded")
    if not added:
        print("  (was already suppressed)")


def cmd_purge(args) -> None:
    from app import config
    from ingest.store import purge_old_posts

    days = args.days if args.days is not None else config.RETENTION_DAYS
    if days <= 0:
        raise SystemExit("retention disabled (RETENTION_DAYS=0); pass --days to force")
    with SessionLocal() as session:
        gone = purge_old_posts(session, days)
    print(f"purged {gone} post(s) older than {days} days")


def cmd_serve(args) -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, reload=args.reload)


def cmd_reset(args) -> None:
    if not args.yes:
        raise SystemExit("refusing to drop tables without --yes")
    Base.metadata.drop_all(engine)
    print("all tables dropped")


def main() -> None:
    parser = argparse.ArgumentParser(prog="manage.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db").set_defaults(func=cmd_init_db)

    p = sub.add_parser("backfill")
    p.add_argument("path")
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_backfill)

    sub.add_parser("regeocode").set_defaults(func=cmd_regeocode)

    p = sub.add_parser("reextract")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--before",
        default=None,
        help="Skip posts already extracted at/after this ISO time "
             "(e.g. 2026-08-06T09:00). Use the moment the prompt or "
             "vocabulary changed, so a resumed run doesn't redo finished work.",
    )
    p.set_defaults(func=cmd_reextract)

    p = sub.add_parser("ingest")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--check-deleted", type=int, default=40)
    p.add_argument(
        "--sources",
        default=None,
        help="Comma list of subreddits; defaults to SUBREDDITS from config",
    )
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser(
        "suppress",
        help="erasure request: delete now, and keep it deleted across scrapes",
    )
    p.add_argument("--post", help="reddit id, or the full permalink")
    p.add_argument("--author", help="username — removes them and any future post")
    p.add_argument("--reason", default="", help="how the request arrived (private)")
    p.set_defaults(func=cmd_suppress)

    p = sub.add_parser("purge", help="delete posts past the retention window")
    p.add_argument("--days", type=int, default=None, help="default: RETENTION_DAYS")
    p.set_defaults(func=cmd_purge)

    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("reset")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
