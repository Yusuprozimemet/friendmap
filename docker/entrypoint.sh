#!/bin/sh
# Container entrypoint. Two shapes:
#
#   serve                 create/verify the schema, then run the API  (default)
#   ingest --days 7       the daily job — same image, different command
#   <anything else>       passed straight to python manage.py
#
# Keep this file LF-only; .gitattributes pins it. A CRLF shebang makes the
# kernel look for an interpreter literally named "/bin/sh\r".
set -eu

case "${1:-serve}" in
  serve)
    # No Alembic yet (see README, Known gaps) — the schema comes from
    # create_all, which is idempotent, and the gazetteer seed is upsert-safe.
    # Set INIT_DB=false once migrations exist.
    if [ "${INIT_DB:-true}" = "true" ]; then
      echo "==> init-db"
      python manage.py init-db
    fi

    echo "==> serving on 0.0.0.0:${PORT:-8000}"
    # --proxy-headers so the app sees https:// behind Render's edge; the
    # rate limiter reads the client IP separately, gated on TRUST_PROXY.
    exec uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --workers "${WEB_CONCURRENCY:-1}" \
      --proxy-headers \
      --forwarded-allow-ips "*"
    ;;
  *)
    exec python manage.py "$@"
    ;;
esac
