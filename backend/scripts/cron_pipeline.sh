#!/bin/bash
# Parallax daily pipeline — run via cron/launchd
# Runs: brief (predictions + signals) → check resolutions → scorecard
#
# Works on macOS and Linux/WSL — auto-detects paths from script location.
#
# Cron schedule (add via `crontab -e`):
#   0 8,20 * * * /path/to/parallax-markets/backend/scripts/cron_pipeline.sh

set -euo pipefail

# Auto-detect paths from script location (works on Mac + WSL)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"
LOG_DIR="${HOME}/parallax-logs"
TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
LOG_FILE="${LOG_DIR}/run-${TIMESTAMP}.log"

mkdir -p "${LOG_DIR}"

# Source env vars from backend/.env
ENV_FILE="${BACKEND_DIR}/.env"
if [ -f "${ENV_FILE}" ]; then
    set -a
    source "${ENV_FILE}"
    set +a
else
    echo "WARNING: No .env file at ${ENV_FILE}" >&2
fi

cd "${BACKEND_DIR}"

echo "=== Parallax pipeline run ${TIMESTAMP} ===" | tee -a "${LOG_FILE}"

# Step 1: Run brief (predictions + market reads + signal evaluation)
echo "[$(date -u)] Running brief..." | tee -a "${LOG_FILE}"
python -m parallax.cli.brief --no-trade --scheduled 2>&1 | tee -a "${LOG_FILE}"

# Step 2: Check resolutions (backfill settled contracts)
echo "[$(date -u)] Checking resolutions..." | tee -a "${LOG_FILE}"
python -m parallax.cli.brief --check-resolutions 2>&1 | tee -a "${LOG_FILE}" || true

# Step 3: Compute daily scorecard
echo "[$(date -u)] Computing scorecard..." | tee -a "${LOG_FILE}"
python -m parallax.cli.brief --scorecard 2>&1 | tee -a "${LOG_FILE}"

echo "[$(date -u)] Pipeline complete." | tee -a "${LOG_FILE}"

# Prune logs older than 30 days
find "${LOG_DIR}" -name "run-*.log" -mtime +30 -delete 2>/dev/null || true
