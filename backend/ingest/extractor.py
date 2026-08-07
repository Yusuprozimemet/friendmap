"""Turns raw posts into structured profiles with an LLM.

Batched on purpose: NVIDIA NIM's free tier rate-limits on requests-per-minute,
not concurrency, so N posts go out as ceil(N/BATCH_SIZE) calls rather than N.
Each item comes back as one JSON object keyed by its index, which survives the
model dropping or reordering an entry far better than a bare array does.
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone

from openai import APIStatusError, APITimeoutError, OpenAI, RateLimitError

from app import config
from app.models import GENDERS, INTEREST_VOCAB, POST_TYPES

# The binding constraint is NIM's request quota, not generation speed, so
# bigger batches are strictly better up to the token budget: 8 posts per call
# is ~25% fewer requests than 6. 8 did time out originally, but that was
# against the old 120s limit — 240s leaves ample headroom.
BATCH_SIZE = 8
REQUEST_TIMEOUT = 240
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.NVIDIA_API_KEY:
            raise SystemExit("NVIDIA_API_KEY is not set — add it to friendsMap/.env")
        # Fail fast rather than hanging a cron run; see Daily-CronJob's notes.
        _client = OpenAI(
            api_key=config.NVIDIA_API_KEY,
            base_url=config.NVIDIA_BASE_URL,
            timeout=REQUEST_TIMEOUT,
            max_retries=0,
        )
    return _client


@dataclass
class Extracted:
    index: int
    post_type: str = "profile"
    age: int | None = None
    gender: str = "unknown"
    location_raw: str | None = None
    lang: str = "en"
    interests: list[str] = field(default_factory=list)
    looking_for: str | None = None
    summary: str = ""
    confidence: float = 0.0
    needs_review: bool = False


PROMPT = """You extract structured data from posts on Dutch friend-finding \
subreddits, where people introduce themselves to find friends. Posts are in \
Dutch or English, often mixed.

For EACH numbered post, output one JSON object on its own line:
{"n": <post number>, "post_type": ..., "age": ..., "gender": ..., "location": ..., \
"lang": ..., "interests": [...], "looking_for": ..., "summary": ..., "confidence": ...}

Field rules:
- post_type: "profile" if a person is introducing themselves to find friends.
  "event" if it's about a specific outing/activity invitation instead.
  "meta" for moderator posts, rules, announcements, community updates.
- age: integer, or null if not stated. For couples, the age of the poster.
- gender: exactly one of "M", "F", "NB", "couple", "unknown". Dutch "man"/"vrouw"
  map to M/F. "25NB" is NB. Two people posting together is "couple".
- location: the most specific Dutch place named — a city ("Zaandam"), else a
  province ("Friesland", "Noord-Holland"), else null. Write it as plain text.
  Do NOT invent one; null is correct when they withheld it.
- lang: "nl" or "en", whichever the post is mostly written in.
- interests: 1-4 tags, ONLY from this list: __VOCAB__
- looking_for: max 12 words on what kind of contact they want.
- summary: ONE English sentence, 12-25 words, describing what makes THIS person
  distinct — their actual hobbies, their situation, who they want to meet.
  Do NOT restate age, gender or city; those are displayed separately.
  Never write "seeking friends" or "looking for friends" — that is true of
  everyone here and carries no information.
  GOOD: "Recently moved for work, climbs three times a week, wants a regular
  hiking group rather than one-offs."
  BAD: "Man seeking local friends." / "Gamer looking for friends."
- confidence: 0.0-1.0, how sure you are about age/gender/location.

Output ONLY the JSON lines, one per post, nothing else."""


def _build_prompt(items: list[dict]) -> str:
    blocks = []
    for i, item in enumerate(items, 1):
        body = (item.get("body") or "")[:1500]
        blocks.append(f"### POST {i}\nTITLE: {item['title']}\nBODY: {body}")
    return "\n\n".join(blocks)


def _coerce(raw: dict) -> Extracted | None:
    try:
        index = int(raw["n"])
    except (KeyError, TypeError, ValueError):
        return None

    post_type = str(raw.get("post_type") or "profile").lower()
    if post_type not in POST_TYPES:
        post_type = "profile"

    gender = str(raw.get("gender") or "unknown")
    if gender not in GENDERS:
        gender = {"m": "M", "f": "F", "nb": "NB"}.get(gender.lower(), "unknown")

    age = raw.get("age")
    try:
        age = int(age) if age is not None else None
    except (TypeError, ValueError):
        age = None
    if age is not None and not (13 <= age <= 99):
        age = None  # out of plausible range = misparse, not a real age

    interests = [
        str(i).lower() for i in (raw.get("interests") or [])
        if str(i).lower() in INTEREST_VOCAB
    ][:4]

    lang = str(raw.get("lang") or "en").lower()
    if lang not in ("nl", "en"):
        lang = "en"

    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0.0

    location = raw.get("location")
    location = str(location).strip() if location else None
    if location and location.lower() in ("null", "none", "unknown", ""):
        location = None

    return Extracted(
        index=index,
        post_type=post_type,
        age=age,
        gender=gender,
        location_raw=location,
        lang=lang,
        interests=interests,
        looking_for=(str(raw["looking_for"]).strip() if raw.get("looking_for") else None),
        summary=str(raw.get("summary") or "").strip(),
        confidence=confidence,
        needs_review=confidence < 0.5,
    )


def _parse(text: str) -> dict[int, Extracted]:
    """Pull JSON objects out of the reply, tolerating prose and code fences."""
    out: dict[int, Extracted] = {}
    for match in re.finditer(r"\{[^{}]*\}", text, re.S):
        try:
            raw = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        item = _coerce(raw)
        if item is not None:
            out[item.index] = item
    return out


def _call(prompt_body: str) -> str:
    """One batch, with backoff.

    NIM's free tier pushes back three ways: 429 for the per-minute request
    quota, 503 "ResourceExhausted" when its shared workers are saturated, and
    plain timeouts when a batch generates slowly. All transient, all retried.
    """
    client = _get_client()
    # str.format is unusable here — the prompt is full of literal JSON braces.
    system = PROMPT.replace("__VOCAB__", ", ".join(INTEREST_VOCAB))
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt_body},
    ]

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=config.NVIDIA_MODEL, messages=messages,
                temperature=0.1, max_tokens=2000,
            )
            return resp.choices[0].message.content or ""
        except (RateLimitError, APIStatusError, APITimeoutError) as exc:
            status = getattr(exc, "status_code", None)
            if isinstance(exc, APIStatusError) and status not in (429, 503):
                raise
            last_error = exc
            wait = 20 * (attempt + 1)
            label = "timeout" if isinstance(exc, APITimeoutError) else str(status or 429)
            print(f"  {label} from NIM, retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"NIM unavailable after 3 attempts: {last_error}")


def extract_batches(items: list[dict]) -> Iterator[dict[str, Extracted]]:
    """Yield one {post id -> Extracted} map per batch, as each call returns.

    A generator rather than one big dict so the caller can commit incrementally:
    on a long backfill that makes progress durable against an interrupt, and
    lets the UI fill up while the run is still going.
    """
    for start in range(0, len(items), BATCH_SIZE):
        chunk = items[start:start + BATCH_SIZE]
        print(f"  extracting {start + 1}-{start + len(chunk)} of {len(items)}...")
        try:
            reply = _call(_build_prompt(chunk))
        except Exception as exc:
            print(f"  batch failed: {exc}")
            yield {}
            continue

        parsed = _parse(reply)
        results: dict[str, Extracted] = {}
        for i, item in enumerate(chunk, 1):
            if i in parsed:
                results[item["id"]] = parsed[i]
            else:
                print(f"  no extraction for post {item['id']}")
        yield results

        if start + BATCH_SIZE < len(items):
            time.sleep(5)  # stay under the per-minute request quota


def extract(items: list[dict]) -> dict[str, Extracted]:
    """Collect every batch into one map. Convenience for small, one-shot runs."""
    merged: dict[str, Extracted] = {}
    for batch in extract_batches(items):
        merged.update(batch)
    return merged


def extracted_at() -> datetime:
    return datetime.now(timezone.utc)
