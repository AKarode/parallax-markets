#!/usr/bin/env bash
# Nightly health summary of Parallax pipeline runs.
# Reports daily successes and failures from error marker directory.

ERROR_DIR="$HOME/parallax-logs/errors"
TODAY=$(date +%Y-%m-%d)

echo "=== Parallax Health Check: $TODAY ==="

ERRORS=$(find "$ERROR_DIR" -name "${TODAY}*.json" 2>/dev/null | wc -l | tr -d ' ')
LOGS=$(find "$HOME/parallax-logs" -maxdepth 1 -name "${TODAY}*.log" 2>/dev/null | wc -l | tr -d ' ')

echo "Runs today: $LOGS"
echo "Failures: $ERRORS"

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "--- Error Details ---"
    cat "$ERROR_DIR"/${TODAY}*.json 2>/dev/null
fi

# Count JSON run outputs (successful scheduled runs)
RUNS=$(find "$HOME/parallax-logs/runs" -name "*.json" -newer "$HOME/parallax-logs/runs" -mtime 0 2>/dev/null | wc -l | tr -d ' ')
echo "Scheduled outputs today: $RUNS"

echo "=== End Health Check ==="
