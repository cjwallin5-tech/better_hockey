#!/bin/zsh
# Morning roster digest: emails every account that turned it on. Run by launchd (see README).
cd "${0:A:h}" || exit 1
mkdir -p logs
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') digest start"
  .venv/bin/python -u digest.py
  rc=$?
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') digest finished (exit $rc)"
  exit $rc
} >> logs/digest.log 2>&1
