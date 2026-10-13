#!/bin/zsh
# Nightly refresh: pull new games and season stats into Postgres. Run by launchd (see README).
cd "${0:A:h}" || exit 1
mkdir -p logs
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ingest start"
  .venv/bin/python -u ingest.py
  rc=$?
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ingest finished (exit $rc)"
  exit $rc
} >> logs/ingest.log 2>&1
