"""Verify the repository ships no real personal data.

Re-checkable evidence for the claim in the README: the sample entries in the
standalone prototype are fabricated, not scraped.

Definitive test: compare its titles and body fragments against the 934 real
posts in the local database. A match means the public repo contains real
people's post text; no match across 934 rows means it was fabricated for the
design mockup.

Avoids regex entirely — the strings are JS single-quoted with escapes, and
hand-rolled splitting is less error-prone here than getting a character class
through two layers of shell quoting.
"""
from __future__ import annotations

import pathlib

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Post

HTML = pathlib.Path("../FriendMap NL (standalone).html")


def js_strings(blob: str, field: str) -> list[str]:
    """Every `field:'...'` value, honouring backslash escapes."""
    out: list[str] = []
    needle = field + ":'"
    i = 0
    while True:
        i = blob.find(needle, i)
        if i < 0:
            return out
        i += len(needle)
        buf: list[str] = []
        while i < len(blob):
            ch = blob[i]
            if ch == "\\" and i + 1 < len(blob):
                nxt = blob[i + 1]
                buf.append("\n" if nxt == "n" else nxt)
                i += 2
                continue
            if ch == "'":
                i += 1
                break
            buf.append(ch)
            i += 1
        out.append("".join(buf))


def main() -> None:
    blob = HTML.read_text(encoding="utf-8", errors="replace")
    if "RAW_PEOPLE = [" not in blob:
        print("no RAW_PEOPLE array found")
        return
    raw = blob.split("RAW_PEOPLE = [", 1)[1]

    titles = [t for t in js_strings(raw, "title") if len(t) >= 6]
    bodies = [b for b in js_strings(raw, "body") if len(b) >= 40]
    print(f"standalone file: {len(titles)} titles, {len(bodies)} bodies")

    with SessionLocal() as s:
        total = s.scalar(select(func.count(Post.reddit_id)))
        print(f"real posts in local db: {total}")

        hits = []
        for t in titles:
            row = s.scalars(select(Post).where(Post.title == t.strip())).first()
            if row:
                hits.append(("exact title", t[:65], row.reddit_id))
        for b in bodies:
            frag = b.strip()[:60]
            row = s.scalars(select(Post).where(Post.body.contains(frag))).first()
            if row:
                hits.append(("body fragment", frag[:65], row.reddit_id))

        print()
        if hits:
            print(f"*** {len(hits)} MATCH(ES) — this is REAL scraped data ***")
            for kind, text, rid in hits[:12]:
                print(f"  {kind}: {text!r} -> {rid}")
        else:
            print("NO match against any of the real posts.")
            print("Consistent with fabricated mockup data, not a real scrape.")


if __name__ == "__main__":
    main()
