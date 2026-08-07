# syntax=docker/dockerfile:1

# One image, one origin. The web app calls the API with relative /api paths
# and the session cookie is SameSite=Lax, so splitting the static site off to
# a second host would mean CORS plus a cross-site cookie. Serving the built
# bundle from FastAPI keeps production the same shape as dev (where Vite
# proxies /api), which is the whole reason the auth code is this small.

# ---------- stage 1: build the React bundle ----------
FROM node:20-alpine AS web

WORKDIR /web
# Copy the manifests alone first so `npm ci` is cached until deps change.
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
# `tsc -b && vite build` — a type error fails the image build, on purpose.
RUN npm run build


# ---------- stage 2: the runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# psycopg[binary] ships wheels, so there is no compiler in this image.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/
COPY --from=web /web/dist /app/static
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Where main.py looks for the bundle. Unset it and the app falls back to the
# JSON root route, which is what a bare `uvicorn` run against a source tree does.
ENV WEB_DIST=/app/static \
    PORT=8000

# Nothing here needs root, and Render will run whatever user the image names.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/logs \
    && chown -R app:app /app
USER app

EXPOSE 8000

# `docker run <image>` serves; `docker run <image> ingest --days 7` runs the
# daily job in the same image, which is what the Render cron job uses.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["serve"]
