#!/usr/bin/env bash
# Install crontab entries for automated Parallax pipeline runs.
# Schedule: 3 brief runs (7AM, 1PM, 9PM), resolution check (11PM), calibration (11:30PM).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRON_SCRIPT="$SCRIPT_DIR/parallax-cron.sh"
HEALTH_SCRIPT="$SCRIPT_DIR/cron-health-check.sh"

# Verify scripts exist
if [ ! -f "$CRON_SCRIPT" ]; then
    echo "ERROR: $CRON_SCRIPT not found" >&2
    exit 1
fi
if [ ! -f "$HEALTH_SCRIPT" ]; then
    echo "ERROR: $HEALTH_SCRIPT not found" >&2
    exit 1
fi

# WSL2 detection: check if running in WSL2 and advise /etc/wsl.conf if needed
if grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
    echo "WSL2 detected."
    if ! grep -q "\[boot\]" /etc/wsl.conf 2>/dev/null || ! grep -q "service cron start" /etc/wsl.conf 2>/dev/null; then
        echo "WARNING: /etc/wsl.conf does not have cron auto-start configured."
        echo "To ensure cron survives WSL2 restarts, add the following to /etc/wsl.conf (requires sudo):"
        echo "  [boot]"
        echo "  command=\"service cron start\""
        echo "Run: sudo bash -c 'printf \"[boot]\\ncommand=\\\"service cron start\\\"\\n\" >> /etc/wsl.conf'"
    else
        echo "WSL2 cron auto-start already configured in /etc/wsl.conf."
    fi
fi

# Build crontab entries (times in user's local timezone)
# D-01 schedule: 3 brief runs at 7:00 AM, 1:00 PM, 9:00 PM
# Resolution check at 11:00 PM, Calibration at 11:30 PM, Health check at 11:45 PM
CRON_ENTRIES="# Parallax automated pipeline
0 7 * * * $CRON_SCRIPT --scheduled --no-trade
0 13 * * * $CRON_SCRIPT --scheduled --no-trade
0 21 * * * $CRON_SCRIPT --scheduled --no-trade
0 23 * * * $CRON_SCRIPT --check-resolutions
30 23 * * * $CRON_SCRIPT --calibration
45 23 * * * $HEALTH_SCRIPT >> \$HOME/parallax-logs/health-\$(date +\\%Y-\\%m-\\%d).log 2>&1"

echo "Will install the following cron entries:"
echo "$CRON_ENTRIES"
echo ""
read -p "Proceed? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    (crontab -l 2>/dev/null | grep -v "parallax"; echo "$CRON_ENTRIES") | crontab -
    echo "Cron entries installed. Verify with: crontab -l"
else
    echo "Aborted."
fi
