"""Central config. Loads friendsMap/.env; env vars win in CI/containers."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # friendsMap/
load_dotenv(ROOT / ".env")

def _normalise_db_url(url: str) -> str:
    """Force the psycopg 3 driver.

    Managed Postgres (Render, Heroku, Fly) hands out `postgres://…` or
    `postgresql://…`, and SQLAlchemy reads a bare `postgresql://` as psycopg2,
    which isn't installed. Rewriting here beats asking every deploy target to
    remember the `+psycopg` suffix.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _normalise_db_url(
    os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://friendmap:friendmap@localhost:5433/friendmap",
    )
)

# Behind a reverse proxy (Render, any CDN) every request arrives from the
# proxy's IP, so the per-IP rate limiter would meter the whole internet as one
# client. On, the limiter reads X-Forwarded-For instead. Leave it off anywhere
# the app is reachable directly — a header the client controls is worthless.
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")

# Sources, in priority order. Comma-separated; the old singular SUBREDDIT is
# still honoured so an existing .env keeps working.
_raw_subs = os.getenv("SUBREDDITS") or os.getenv("SUBREDDIT") or "makenewfriendsNL,Vriendenmaken"
SUBREDDITS = [s.strip().removeprefix("r/") for s in _raw_subs.split(",") if s.strip()]
# Used only where a single source has to be assumed — e.g. an old backfill
# payload that predates the subreddit field.
SUBREDDIT = SUBREDDITS[0]
REDDIT_USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT", "friendmap-nl/1.0 (daily subreddit digest)"
)

# Posts older than this are still stored, just hidden by the UI's default filter.
DEFAULT_PERIOD_DAYS = 30

# API rate limit, per client IP. Set well above human use on purpose: the
# bucket is shared by everyone behind one NAT, and a busy session already
# spends a request per filter change. A scrape loop runs hundreds a minute
# and still hits the wall inside a few seconds.
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "120"))
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "60"))

# --- Sign-in with Google -------------------------------------------------
# Identity only, no password storage. Browsing stays anonymous; an account is
# for the things that need one (saved people, alerts). Unset creds simply
# disable the feature — the app runs fine without them.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
# Must match a redirect URI registered in the Google Cloud console exactly.
OAUTH_REDIRECT_URL = os.getenv(
    "OAUTH_REDIRECT_URL", "http://localhost:5173/api/auth/google/callback"
)
# Where to land the browser after the round trip.
WEB_ORIGIN = os.getenv("WEB_ORIGIN", "http://localhost:5173")
# Signs the session cookie. Rotating it logs everyone out, which is the
# intended emergency lever.
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
SESSION_COOKIE = "friendmap_session"
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", str(60 * 60 * 24 * 30)))

AUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and SESSION_SECRET)

# Keys the per-person identifier that saves and notes hang off. DURABLE:
# rotating it orphans every saved row, so treat it like a database password,
# not like a cache key.
PERSON_KEY_SECRET = os.getenv("PERSON_KEY_SECRET", "")

# --- Email alerts --------------------------------------------------------
# console | smtp | resend. Console prints instead of sending, which is the
# right default: nothing goes out by accident before a transport is chosen.
MAIL_BACKEND = os.getenv("MAIL_BACKEND", "console")
MAIL_FROM = os.getenv("MAIL_FROM", "FriendMap NL <alerts@localhost>")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() != "false"
SMTP_SSL = os.getenv("SMTP_SSL", "false").lower() == "true"

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

#: Never let one person's saved searches turn the nightly job into a scraper.
MAX_SAVED_SEARCHES = int(os.getenv("MAX_SAVED_SEARCHES", "5"))
#: How many people a single digest lists before it just says "and N more".
ALERT_MAX_PEOPLE = int(os.getenv("ALERT_MAX_PEOPLE", "8"))

if AUTH_ENABLED and not PERSON_KEY_SECRET:
    raise RuntimeError(
        "PERSON_KEY_SECRET must be set when Google sign-in is enabled — "
        "saved people key off it. Generate one with:\n"
        '  python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )
