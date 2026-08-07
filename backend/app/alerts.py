"""Saved-search alerts: find newly matching people, tell their owner once.

Runs at the tail of the daily ingest, after new profiles land.

Two rules shape everything here:

* **One digest per user, not per search.** Three saved searches finding
  someone must not be three emails.
* **Record only after a successful send.** `alerts_sent` is written after the
  mail is accepted, so a transport failure retries tomorrow instead of
  silently swallowing the match forever.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, mail
from app.models import AlertSent, SavedSearch, User
from app.schemas import PersonOut
from app.search import SearchParams
from app.search import run as run_search

_UNSUBSCRIBE_SALT = "friendmap-alert-unsubscribe"

CADENCE_DAYS = {"daily": 1, "weekly": 7}


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(config.SESSION_SECRET, salt=_UNSUBSCRIBE_SALT)


def unsubscribe_token(search_id: int) -> str:
    """Signed, so a token can only switch off the search it was minted for."""
    return _serializer().dumps({"sid": search_id})


def read_unsubscribe_token(token: str) -> int | None:
    try:
        payload = _serializer().loads(token)
    except BadSignature:
        return None
    sid = payload.get("sid")
    return sid if isinstance(sid, int) else None


def _is_due(search: SavedSearch, now: datetime) -> bool:
    every = CADENCE_DAYS.get(search.cadence)
    if every is None:  # 'off'
        return False
    if search.last_run_at is None:
        return True
    last = search.last_run_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(days=every) - timedelta(hours=1)


def _describe(person: PersonOut) -> str:
    who = "".join(
        part
        for part in [
            str(person.age or ""),
            person.gender if person.gender != "unknown" else "",
        ]
    )
    where = person.city or (f"~{person.province}" if person.province else "no location given")
    summary = (person.summary or person.title or "").strip()
    if len(summary) > 110:
        summary = summary[:107].rstrip() + "…"
    return f"- {who or '?'} · {where}\n  {summary}"


def _body(
    blocks: list[tuple[SavedSearch, list[PersonOut]]],
) -> str:
    lines: list[str] = []
    for search, people in blocks:
        lines.append(f'"{search.name}" — {len(people)} new')
        shown = people[: config.ALERT_MAX_PEOPLE]
        lines.extend(_describe(p) for p in shown)
        if len(people) > len(shown):
            lines.append(f"  …and {len(people) - len(shown)} more")
        lines.append(f"  See them: {config.WEB_ORIGIN}/")
        lines.append(
            "  Stop alerts for this search: "
            f"{config.WEB_ORIGIN}/api/alerts/unsubscribe?token={unsubscribe_token(search.id)}"
        )
        lines.append("")
    lines.append(
        "These are public posts from Dutch friend-finding subreddits. "
        "FriendMap NL never contacts anyone on your behalf."
    )
    return "\n".join(lines)


def run_alerts(session: Session, now: datetime | None = None) -> int:
    """Send due digests. Returns the number of emails actually sent."""
    if not config.AUTH_ENABLED:
        return 0

    now = now or datetime.now(timezone.utc)
    searches = session.scalars(
        select(SavedSearch).where(SavedSearch.cadence != "off")
    ).all()

    per_user: dict[int, list[tuple[SavedSearch, list[PersonOut]]]] = defaultdict(list)
    ran: list[SavedSearch] = []

    for search in searches:
        if not _is_due(search, now):
            continue
        ran.append(search)

        params = SearchParams.from_dict(search.filters)
        # A saved search is about finding people, not re-reading your own
        # list, so the personal state filter is ignored — but hidden people
        # still stay hidden.
        params.state = None
        params.include_hidden = False
        people = run_search(session, params, user_id=search.user_id)

        already = {
            key
            for (key,) in session.execute(
                select(AlertSent.person_key).where(
                    AlertSent.saved_search_id == search.id
                )
            ).all()
        }
        fresh = [p for p in people if p.person_key and p.person_key not in already]
        if fresh:
            per_user[search.user_id].append((search, fresh))

    sent_count = 0
    for user_id, blocks in per_user.items():
        user = session.get(User, user_id)
        if user is None or not user.email:
            continue

        total = sum(len(people) for _, people in blocks)
        where = blocks[0][0].name if len(blocks) == 1 else "your saved searches"
        subject = f"{total} new {'person' if total == 1 else 'people'} — {where}"

        if not mail.send(user.email, subject, _body(blocks)):
            # Leave alerts_sent untouched so tomorrow's run tries again.
            continue

        sent_count += 1
        for search, people in blocks:
            for person in people:
                session.add(
                    AlertSent(
                        saved_search_id=search.id,
                        person_key=person.person_key,
                        sent_at=now,
                    )
                )
            search.last_match_at = now

    # last_run_at advances for every search considered, including the ones
    # with nothing new — otherwise a quiet search re-runs on every job.
    for search in ran:
        search.last_run_at = now

    session.commit()
    return sent_count
