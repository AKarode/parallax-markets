# Jarvis Operations Runbook

Day-to-day commands for the Parallax deployment on Jarvis.

## Quick reference

```bash
# Service health
ssh Jarvis 'systemctl status parallax-api.service'
ssh Jarvis 'curl -sf http://127.0.0.1:8000/api/health | jq .'

# Timer status (next scheduled run)
ssh Jarvis 'systemctl list-timers parallax-brief.timer'

# Tail logs (last 100 lines, follow)
ssh Jarvis 'journalctl -u parallax-api.service -n 100 -f'
ssh Jarvis 'journalctl -u parallax-brief.service -n 100'

# Memory / swap usage
ssh Jarvis 'free -h; echo; systemd-cgtop -n 1 --depth 2 -m | grep -E "parallax|hermes" | head'
```

## Start / stop services

```bash
# API service
ssh Jarvis 'systemctl start parallax-api.service'
ssh Jarvis 'systemctl stop parallax-api.service'
ssh Jarvis 'systemctl restart parallax-api.service'

# Brief timer (8am + 8pm UTC)
ssh Jarvis 'systemctl start parallax-brief.timer'
ssh Jarvis 'systemctl stop parallax-brief.timer'

# Manually trigger brief NOW
ssh Jarvis 'systemctl start parallax-brief.service'
```

## Tail a live brief run

```bash
ssh Jarvis 'systemctl start parallax-brief.service && journalctl -u parallax-brief.service -f'
```

## Access the API from your Mac

API binds to `127.0.0.1:8000` on Jarvis (not exposed to the internet). To reach it:

```bash
# One-shot
ssh Jarvis 'curl -s http://127.0.0.1:8000/api/health' | jq .

# Persistent tunnel for browser/dashboard access
ssh -L 8000:127.0.0.1:8000 -N -f Jarvis
# Now open http://localhost:8000/docs in your Mac browser
# Kill: pkill -f 'ssh -L 8000:127.0.0.1:8000'
```

## Enable paper trading on Kalshi demo

By default, `parallax-brief.service` runs with `--no-trade` for safety. To enable Kalshi demo paper trading:

```bash
ssh Jarvis 'sed -i "s|--no-trade||" /etc/systemd/system/parallax-brief.service
            systemctl daemon-reload'
```

The Kalshi PEM at `/root/.parallax/kalshi_private_key.pem` is the demo key — paper-trading-only. Live trading requires additionally setting `live_execution_authorized: true` in `config/runtime.yaml` (intentional friction).

## Change the cron schedule

Edit `OnCalendar` lines in `/etc/systemd/system/parallax-brief.timer`, then:

```bash
ssh Jarvis 'systemctl daemon-reload && systemctl restart parallax-brief.timer'
```

Common patterns:
- `OnCalendar=*-*-* 08,20:00 UTC` — twice daily (current)
- `OnCalendar=hourly` — every hour
- `OnCalendar=*-*-* */2:00 UTC` — every 2 hours

## DuckDB inspection

```bash
ssh Jarvis 'ls -lh /root/parallax-data/'
ssh Jarvis 'cd /root/parallax-markets/backend && .venv/bin/python -c "
import duckdb
c = duckdb.connect(\"/root/parallax-data/parallax.duckdb\")
print(c.execute(\"SELECT COUNT(*) FROM signal_ledger\").fetchone())
print(c.execute(\"SELECT model_id, signal, COUNT(*) FROM signal_ledger GROUP BY model_id, signal\").fetchall())
"'
```

## Backup DuckDB

```bash
# One-off backup to Mac
scp Jarvis:/root/parallax-data/parallax.duckdb \
    ~/parallax-backups/parallax-$(date +%F).duckdb

# Or compressed
ssh Jarvis 'gzip -c /root/parallax-data/parallax.duckdb' > ~/parallax-backups/parallax-$(date +%F).duckdb.gz
```

To automate daily backups, add a cron entry on your Mac:

```cron
0 3 * * * scp Jarvis:/root/parallax-data/parallax.duckdb ~/parallax-backups/parallax-$(date +\%F).duckdb && find ~/parallax-backups -mtime +30 -delete
```

## Rotate / update secrets

```bash
# Edit env in place
ssh Jarvis 'vim /root/.parallax/env'
# OR overwrite from local
scp ./new.env Jarvis:/root/.parallax/env
ssh Jarvis 'chmod 600 /root/.parallax/env && systemctl restart parallax-api.service'

# Rotate Kalshi PEM
scp ~/.kalshi/new_private_key.pem Jarvis:/root/.parallax/kalshi_private_key.pem
ssh Jarvis 'chmod 600 /root/.parallax/kalshi_private_key.pem && systemctl restart parallax-api.service'
```

**Never** put secrets in `/root/parallax-markets/` (the source tree) — they would be visible to `git status` and could be accidentally committed.

## Memory / contention monitoring

```bash
# Top memory consumers on Jarvis
ssh Jarvis 'ps aux --sort=-%mem | head -10'

# Per-slice resource usage
ssh Jarvis 'systemd-cgtop -n 3 --depth 2 -m'

# Swap pressure (anything > 500 MB used sustained = consider resize)
ssh Jarvis 'free -h && cat /proc/pressure/memory'
```

If swap usage climbs above 500 MB during normal operation, upgrade the droplet (see `JARVIS-DEPLOYMENT.md` → "Resource-resize triggers").

## Re-deploy after code changes

See `JARVIS-DEPLOYMENT.md` → "Re-deploying after Mac-side changes".

## Tail the latest brief

```bash
ssh Jarvis 'journalctl -u parallax-brief.service -n 200 --since "1 hour ago"'
```
