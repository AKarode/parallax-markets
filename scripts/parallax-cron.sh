#!/usr/bin/env bash
# Cron wrapper for automated Parallax pipeline runs.
# Sources environment, runs command, logs output, writes error marker on failure.
set -euo pipefail

# Source environment variables (API keys etc.)
# T-03-01 mitigation: never log key values, only check presence
if [ -f /tmp/parallax-env.sh ]; then
    source /tmp/parallax-env.sh
else
    echo "ERROR: /tmp/parallax-env.sh not found. Create it with required env vars." >&2
    exit 1
fi

# Verify critical env vars are set (presence only, never log values)
for var in ANTHROPIC_API_KEY KALSHI_API_KEY KALSHI_PRIVATE_KEY_PATH; do
    if [ -z "${!var:-}" ]; then
        echo "WARNING: $var is not set" >&2
    fi
done

TIMESTAMP=$(date +%Y-%m-%d-%H%M)
LOG_DIR="$HOME/parallax-logs"
ERROR_DIR="$LOG_DIR/errors"
mkdir -p "$LOG_DIR" "$ERROR_DIR" "$LOG_DIR/runs"

RUN_LOG="$LOG_DIR/$TIMESTAMP.log"
CMD="$@"

echo "[$TIMESTAMP] Running: parallax.cli.brief $CMD" >> "$RUN_LOG"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR/backend"

if python -m parallax.cli.brief $CMD >> "$RUN_LOG" 2>&1; then
    echo "[$TIMESTAMP] SUCCESS" >> "$RUN_LOG"
else
    EXIT_CODE=$?
    echo "[$TIMESTAMP] FAILED (exit $EXIT_CODE)" >> "$RUN_LOG"
    echo "{\"timestamp\": \"$TIMESTAMP\", \"command\": \"$CMD\", \"exit_code\": $EXIT_CODE}" > "$ERROR_DIR/$TIMESTAMP.json"
fi
