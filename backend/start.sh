#!/bin/sh
# Railway start command for every backend-folder service. Which job runs depends on the JOB variable:
#   JOB=ingest  nightly refresh (cron service): pull new games, then grade/store predictions
#   JOB=digest  morning roster digest email (cron service)
#   (unset)     the web API
case "$JOB" in
  ingest)
    python -u ingest.py
    rc=$?
    python -u predictions.py   # runs even if the ingest failed, like run_ingest.sh
    exit $rc
    ;;
  digest)
    exec python -u digest.py
    ;;
  "")
    exec uvicorn api:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips='*'
    ;;
  *)
    echo "Unknown JOB: $JOB" >&2
    exit 2
    ;;
esac
