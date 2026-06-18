#!/usr/bin/env bash
# Auto-restarting guard for backup_forum.py.
# Resumes scraping whenever the process dies, until the forum is fully archived.
#
# Usage: ./run_forum_guard.sh <forum_name> <output_dir> [concurrency]

set -u

FORUM="${1:?forum name required}"
OUTDIR="${2:?output dir required}"
CONCURRENCY="${3:-8}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD_LOG="$OUTDIR/_guard.log"

mkdir -p "$OUTDIR"

attempt=0
backoff=15

log() { echo "[guard $(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$GUARD_LOG"; }

log "Guard started: forum=$FORUM outdir=$OUTDIR concurrency=$CONCURRENCY"

while true; do
  attempt=$((attempt + 1))
  log "=== attempt #$attempt: launching backup_forum.py ==="

  run_log="$OUTDIR/_guard_run_${attempt}.out"
  started=$(date +%s)
  python3 -u "$SCRIPT_DIR/backup_forum.py" "$FORUM" "$OUTDIR" --concurrency "$CONCURRENCY" 2>&1 | tee "$run_log"
  code=${PIPESTATUS[0]}
  ran=$(( $(date +%s) - started ))

  if grep -q "No pending threads to process" "$run_log"; then
    log "All threads archived. Done. (exit_code=$code)"
    break
  fi

  # If the run made real progress (lasted a while), reset backoff.
  if [ "$ran" -gt 120 ]; then backoff=15; fi

  log "Process exited (exit_code=$code, ran ${ran}s) but archive incomplete. Restarting in ${backoff}s ..."
  sleep "$backoff"
  # gentle exponential backoff, capped at 5 min, to ease off rate limiting
  backoff=$(( backoff * 2 ))
  if [ "$backoff" -gt 300 ]; then backoff=300; fi
done

log "Guard finished."
