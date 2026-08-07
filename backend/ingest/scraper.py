"""Reddit scraping via public Atom feeds.

Reddit's .json listings now 403 for non-browser clients, but the per-subreddit
RSS/Atom feeds stay open and need no credentials — only a descriptive
User-Agent. They 429 aggressively on bursts, hence the backoff.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from app import config
from ingest.textclean import strip_feed_footer

ATOM = "{http://www.w3.org/2005/Atom}"
# The listing is not capped at 1000 items — paging reaches the whole subreddit
# (772 posts back to Dec 2023 when measured). The loop exits on the date cutoff,
# so this is only a runaway guard.
MAX_PAGES = 12
# Reddit 429s hard on back-to-back page fetches; 3s between pages roughly halves
# the number of retries on a deep backfill.
PAGE_DELAY = 3

_session = requests.Session()
_session.headers["User-Agent"] = config.REDDIT_USER_AGENT


def _text(entry: ET.Element, tag: str) -> str:
    el = entry.find(f"{ATOM}{tag}")
    return (el.text or "").strip() if el is not None and el.text else ""


def _fetch_page(subreddit: str, path: str, params: dict) -> list[ET.Element]:
    url = f"https://www.reddit.com/r/{subreddit}/{path}.rss"
    for attempt in range(4):
        resp = _session.get(url, params=params, timeout=25)
        if resp.status_code == 200:
            try:
                return ET.fromstring(resp.content).findall(f"{ATOM}entry")
            except ET.ParseError as exc:
                print(f"  [{path}] parse error: {exc}")
                return []
        if resp.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"  [{subreddit}/{path}] 429, sleeping {wait}s")
            time.sleep(wait)
            continue
        print(f"  [{subreddit}/{path}] HTTP {resp.status_code}")
        return []
    return []


def _entry_to_post(entry: ET.Element, subreddit: str) -> dict | None:
    raw_id = _text(entry, "id").rsplit("_", 1)[-1]
    if not raw_id:
        return None

    published = _text(entry, "published") or _text(entry, "updated")
    if not published:
        return None

    link = entry.find(f"{ATOM}link")
    author_el = entry.find(f"{ATOM}author")
    name_el = author_el.find(f"{ATOM}name") if author_el is not None else None
    author = (name_el.text or "").strip() if name_el is not None else ""

    body = strip_feed_footer(
        BeautifulSoup(_text(entry, "content"), "html.parser").get_text("\n", strip=True)
    )

    return {
        "id": raw_id,
        "subreddit": subreddit,
        "author": author.removeprefix("/u/"),
        "title": _text(entry, "title"),
        "body": body,
        "url": link.get("href", "") if link is not None else "",
        "posted_at": datetime.fromisoformat(published).astimezone(timezone.utc),
    }


def fetch_one(subreddit: str, days: int = 7) -> list[dict]:
    """Newest posts from one subreddit back to `days` ago, deduped by id."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries: list[ET.Element] = []
    after = None

    for _page in range(MAX_PAGES):
        params = {"limit": 100}
        if after:
            params["after"] = after
        page_entries = _fetch_page(subreddit, "new", params)
        if not page_entries:
            break
        entries.extend(page_entries)

        oldest = min(
            (_text(e, "published") or _text(e, "updated")) for e in page_entries
        )
        next_after = _text(page_entries[-1], "id")
        if not next_after or next_after == after:
            break  # cursor stopped advancing = end of listing
        after = next_after
        if datetime.fromisoformat(oldest) < cutoff:
            break
        time.sleep(PAGE_DELAY)

    posts: dict[str, dict] = {}
    for entry in entries:
        post = _entry_to_post(entry, subreddit)
        if post and post["posted_at"] >= cutoff:
            posts.setdefault(post["id"], post)

    return sorted(posts.values(), key=lambda p: p["posted_at"], reverse=True)


def fetch(days: int = 7, subreddits: list[str] | None = None) -> list[dict]:
    """Every configured source, newest first.

    Deduped by post id across sources — a crosspost carries the same id, and
    whichever source is listed first in config wins. People who post the same
    appeal to both subreddits are collapsed later, by author.
    """
    subs = subreddits or config.SUBREDDITS
    posts: dict[str, dict] = {}

    for i, sub in enumerate(subs):
        if i:
            time.sleep(PAGE_DELAY)  # don't roll straight into the next 429
        found = fetch_one(sub, days=days)
        print(f"  r/{sub}: {len(found)} posts in window")
        for post in found:
            posts.setdefault(post["id"], post)

    return sorted(posts.values(), key=lambda p: p["posted_at"], reverse=True)


def is_alive(url: str) -> bool:
    """True if the permalink still resolves. Errors count as alive (fail-safe)."""
    try:
        resp = _session.head(url, timeout=15, allow_redirects=True)
        if resp.status_code == 405:  # some hosts reject HEAD
            resp = _session.get(url, timeout=20)
        return resp.status_code != 404
    except requests.RequestException:
        return True
