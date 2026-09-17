# Jarvis Incident Runbook

Diagnostic + recovery procedures when something on Jarvis goes wrong.

## Symptom: `/api/health` returns 500 or connection refused

1. **Check the service is running**:
   ```bash
   ssh Jarvis 'systemctl status parallax-api.service'
   ```
2. **If "inactive" — restart**:
   ```bash
   ssh Jarvis 'systemctl restart parallax-api.service'
   ```
3. **If it keeps crashing — check logs**:
   ```bash
   ssh Jarvis 'journalctl -u parallax-api.service -n 100 --no-pager'
   ```
4. **Common root causes**:
   - Env file unreadable → `ls -l /root/.parallax/env` (must be `-rw------- root root`)
   - DuckDB locked (another process holding it) → `lsof /root/parallax-data/parallax.duckdb`
   - OOM kill → check `dmesg -T | grep -i oom` and `journalctl -k --since "1 hour ago" | grep -i 'killed process'`

## Symptom: brief.service is failing

1. **Pull last failure**:
   ```bash
   ssh Jarvis 'journalctl -u parallax-brief.service -n 200 --no-pager'
   ```
2. **Re-run interactively** to see full output:
   ```bash
   ssh Jarvis 'cd /root/parallax-markets/backend && set -a && . /root/.parallax/env && set +a && .venv/bin/python -m parallax.cli.brief --dry-run'
   ```
3. **Common root causes**:
   - Anthropic API key invalid / rate-limited → check usage at console.anthropic.com
   - Kalshi PEM not loadable → `openssl rsa -in /root/.parallax/kalshi_private_key.pem -check -noout`
   - GDELT API 429 (rate limit) → known intermittent, retry next cron
   - Out-of-memory during predictions → check `dmesg`; consider lowering ensemble size or upgrading droplet

## Symptom: Jarvis is unresponsive / slow

1. **SSH still works?** If yes:
   ```bash
   ssh Jarvis 'free -h; uptime; top -bn1 | head -15'
   ```
2. **If memory exhausted**: parallax + hermes may be fighting. Check the slice cap.
   ```bash
   ssh Jarvis 'systemctl status parallax.slice; systemd-cgtop -n 1 --depth 2 -m'
   ```
3. **Emergency stop** to free memory immediately:
   ```bash
   ssh Jarvis 'systemctl stop parallax-brief.timer parallax-api.service'
   ```
4. **If SSH refuses**: use DigitalOcean web console to reboot (`Power → Reboot`). After reboot, services come up automatically (they're `enabled`).

## Symptom: swap usage climbing

```bash
ssh Jarvis 'free -h'
# If Swap "used" > 500 MB sustained:
#   1. Identify the heavy process: ps aux --sort=-%mem | head -5
#   2. If it's a runaway brief.py: systemctl stop parallax-brief.timer
#   3. If it's Hermes + Parallax both legitimately busy: resize droplet (see DEPLOYMENT)
```

## Symptom: DuckDB file corruption

```bash
# Verify integrity
ssh Jarvis 'cd /root/parallax-markets/backend && .venv/bin/python -c "
import duckdb
c = duckdb.connect(\"/root/parallax-data/parallax.duckdb\", read_only=True)
print(c.execute(\"PRAGMA database_size\").fetchall())
print(c.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema = \\047main\\047\").fetchall())
"'

# If corrupted, restore from latest backup
scp ~/parallax-backups/parallax-YYYY-MM-DD.duckdb Jarvis:/root/parallax-data/parallax.duckdb
ssh Jarvis 'systemctl restart parallax-api.service'
```

## Symptom: secret leaked / suspected compromise

1. **Rotate immediately**:
   - Generate new Anthropic API key at console.anthropic.com (revoke old)
   - Generate new Kalshi API key + PEM at kalshi.com/account/api
2. **Update local + Jarvis** per `JARVIS-OPERATIONS.md` → "Rotate / update secrets"
3. **Audit git history** for accidental commits:
   ```bash
   cd ~/Personal Projects/parallax-markets
   git log --all -p -- backend/.env '.env' 2>&1 | head -50
   ```
   If anything leaked, force-rotate everything and rewrite history with `git filter-repo`.

## Symptom: Hermes / Syncthing OOM-killed by Parallax

This should NOT happen because of the `parallax.slice` 1.2 GB cap. If it does:

1. Verify the slice is actually applied:
   ```bash
   ssh Jarvis 'systemctl show parallax-api.service | grep -E "Slice|Memory"'
   ssh Jarvis 'cat /sys/fs/cgroup/parallax.slice/memory.max'  # should be ~1.26e9
   ```
2. If the slice cap isn't binding, the unit file may have been bypassed. Re-apply:
   ```bash
   ssh Jarvis 'systemctl daemon-reload && systemctl restart parallax-api.service'
   ```
3. Long-term: upgrade the droplet (1.9 GB is too tight for Hermes + Parallax + headroom).

## Symptom: parallax-api.service can't bind port 8000

Means some other process grabbed 8000. Check:

```bash
ssh Jarvis 'ss -tnlp | grep 8000'
```

Likely Hermes plugin or something else snuck in. Two fixes:

- Kill the squatter (if it's safe to)
- Change Parallax's port: edit `/etc/systemd/system/parallax-api.service` `ExecStart` line, change `--port 8000` to `--port 8100`, then `systemctl daemon-reload && systemctl restart parallax-api.service`.

## Useful one-liners

```bash
# Today's signal count
ssh Jarvis 'cd /root/parallax-markets/backend && .venv/bin/python -c "
import duckdb
c = duckdb.connect(\"/root/parallax-data/parallax.duckdb\")
print(c.execute(\"SELECT signal, COUNT(*) FROM signal_ledger WHERE created_at >= CURRENT_DATE GROUP BY signal\").fetchall())
"'

# Last brief outcome
ssh Jarvis 'journalctl -u parallax-brief.service --since today | grep -E "^(BUY_|SELL_|HOLD|REFUSED|ERROR)" | tail -20'

# Disk usage trend
ssh Jarvis 'du -sh /root/parallax-data /root/parallax-markets /root/.parallax /root/vault'
```
