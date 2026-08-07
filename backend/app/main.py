"""FastAPI entrypoint."""
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import PlainTextResponse

from app import alerts, auth, config
from app.db import get_session
from app.models import SavedSearch
from app.ratelimit import RateLimitMiddleware
from app.routers import me, profiles, stats

app = FastAPI(
    title="FriendMap NL",
    description="Structured, mapped view of public Dutch friend-finding subreddits.",
    version="0.1.0",
)

app.add_middleware(
    RateLimitMiddleware,
    rpm=config.RATE_LIMIT_RPM,
    burst=config.RATE_LIMIT_BURST,
    trust_proxy=config.TRUST_PROXY,
)

# Local dev only: the Vite dev server runs on a different port. Note the app
# is normally reached *through* Vite's /api proxy, so the browser sees one
# origin and the session cookie needs no cross-site relaxation. In the
# container the same is true for a different reason — FastAPI serves the
# bundle itself — so this list stays a dev affordance and nothing more.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Signed cookie, no server-side session store. `lax` still allows the cookie
# to ride along on Google's top-level redirect back to us, which is what the
# OAuth callback needs, while blocking it on cross-site subrequests.
if config.AUTH_ENABLED:
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.SESSION_SECRET,
        session_cookie=config.SESSION_COOKIE,
        max_age=config.SESSION_MAX_AGE,
        same_site="lax",
        https_only=config.WEB_ORIGIN.startswith("https://"),
    )


# These posts are already public on Reddit; what this app adds is aggregation.
# A search engine indexing 500-odd people's posts under one roof is the actual
# harm here, so nothing served from this origin is indexable.
@app.middleware("http")
async def no_index(request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


app.include_router(profiles.router)
app.include_router(stats.router)
app.include_router(auth.router)
app.include_router(me.router)


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots() -> str:
    return "User-agent: *\nDisallow: /\n"


@app.get("/api/alerts/unsubscribe", response_class=PlainTextResponse)
def unsubscribe(token: str, session: Session = Depends(get_session)) -> str:
    """One click, no login — the link has to work from an email client.

    The token is signed and names a single saved search, so it can only ever
    switch off the one it was minted for.
    """
    search_id = alerts.read_unsubscribe_token(token)
    if search_id is None:
        raise HTTPException(400, "This unsubscribe link isn't valid.")
    row = session.get(SavedSearch, search_id)
    if row is None:
        return "That saved search no longer exists — you won't hear about it again."
    row.cadence = "off"
    session.commit()
    return (
        f'Alerts for "{row.name}" are off. '
        "You can turn them back on from your account page."
    )


@app.get("/healthz", response_class=PlainTextResponse, include_in_schema=False)
def healthz() -> str:
    """Liveness only — deliberately does not touch Postgres.

    Render restarts a service whose health check fails. Tying that to the
    database would turn a brief DB blip into a restart loop, which fixes
    nothing and loses the rate-limiter state on the way.
    """
    return "ok"


# --- the web app ----------------------------------------------------------
# Mounted last so every route above (including /docs, /robots.txt and the
# routers) is matched first; Starlette tries routes in registration order.
# WEB_DIST is set in the image; from a source checkout it finds web/dist if
# you've run `npm run build`, and otherwise falls back to the JSON root.
_DIST = Path(os.getenv("WEB_DIST") or (config.ROOT / "web" / "dist"))

if (_DIST / "index.html").is_file():
    # html=True serves index.html for "/" and 404s anything else, which is
    # right here: the app keeps all its state in the query string, so there
    # are no client-side routes needing a catch-all rewrite.
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")
else:
    @app.get("/")
    def root():
        return {"app": "FriendMap NL", "docs": "/docs"}
