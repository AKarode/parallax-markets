# Jarvis VPS Deployment

Deployment of Parallax onto the existing Jarvis DigitalOcean droplet alongside Hermes.

## Target

| Item | Value |
|---|---|
| Host | Jarvis (DO droplet) |
| Public IP | `137.184.220.66` |
| OS | Ubuntu 24.04.3 LTS |
| Resources | 1 vCPU / 1.9 GB RAM / 48 GB SSD (29 GB free) |
| Python | 3.12.3 (system) |
| Coexists with | Hermes Agent (~700 MB), Syncthing (~32 MB) |

## Layout on Jarvis

```
/root/parallax-markets/      # Source tree (rsynced from Mac)
/root/parallax-markets/backend/.venv/   # Python venv, isolated
/root/parallax-data/         # DuckDB file (mounted independently)
/root/.parallax/             # Secrets (chmod 700)
  ├── env                    # API keys (chmod 600)
  └── kalshi_private_key.pem # RSA PEM (chmod 600)
/etc/systemd/system/
  ├── parallax.slice         # Memory-bounded slice (1.2 GB cap)
  ├── parallax-api.service   # FastAPI on 127.0.0.1:8000
  ├── parallax-brief.service # Pipeline (oneshot)
  └── parallax-brief.timer   # 08:00 + 20:00 UTC
```

## Memory budget

| Process | Steady | Burst |
|---|---|---|
| Hermes ecosystem | 700 MB | 1.0 GB |
| Syncthing + system | 350 MB | 400 MB |
| Parallax API (idle) | 150 MB | 250 MB |
| Parallax brief (during cron) | 0 | 600-800 MB |
| **Total** | 1.2 GB | 2.4 GB (spills to 2 GB swap) |

Parallax is capped at 1.2 GB via `parallax.slice`. With 2 GB swapfile added at deploy time, brief.py bursts spill to swap rather than OOM-killing Hermes.

## What was done (initial setup)

1. **2 GB swap** added at `/swapfile`, persisted in `/etc/fstab`, `vm.swappiness=10`.
2. **APT packages**: `python3.12-venv`, `python3-pip`, `build-essential`, `rsync`.
3. **Directories**: `/root/parallax-markets`, `/root/parallax-data`, `/root/.parallax` (chmod 700).
4. **Source**: rsync of local working tree (excludes `.venv`, `__pycache__`, `*.duckdb`, `.env`, `node_modules`, build artifacts).
5. **Python venv**: `python3.12 -m venv .venv` + `pip install -e .` (production only, no `[dev]`).
6. **Secrets transferred via scp** (never echoed to logs):
   - Kalshi RSA PEM → `/root/.parallax/kalshi_private_key.pem` (chmod 600)
   - .env → `/root/.parallax/env` (chmod 600), with `KALSHI_PRIVATE_KEY_PATH` and `DUCKDB_PATH` rewritten to Jarvis paths.
7. **Systemd units** installed + enabled (see Layout above).
8. **Smoke test**: `python -m parallax.cli.brief --dry-run` completed end-to-end.
9. **API service started**, `/api/health` returns 200 OK, `kalshi_configured: true`, `data_environment: demo`, `live_execution_authorized: false`.

## Safety defaults

- `parallax-brief.service` calls `brief.py --no-trade` — runs the full pipeline but **never executes orders**, even on Kalshi demo. Change to `brief.py` (no flag) when ready for paper trading.
- `live_execution_authorized: false` (kill switch). Live execution requires writing `config/runtime.yaml` per Parallax's runtime config gate.
- API binds to `127.0.0.1` only — not exposed to the internet. Access via SSH tunnel or local-loopback from on-droplet processes.

## Re-deploying after Mac-side changes

```bash
# From Mac repo root
rsync -az --delete \
  --exclude='.git/objects/pack/*.idx' \
  --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.venv' --exclude='node_modules' \
  --exclude='*.duckdb' --exclude='*.duckdb.wal' \
  --exclude='.env' --exclude='backend/.env' \
  --exclude='frontend/dist' --exclude='data/' \
  ./ Jarvis:/root/parallax-markets/

ssh Jarvis 'cd /root/parallax-markets/backend && .venv/bin/pip install -q -e . && systemctl restart parallax-api.service'
```

## Resource-resize triggers

If you observe sustained swap usage > 500 MB or any OOM event, upgrade the droplet:

```bash
# DigitalOcean dashboard or doctl
doctl compute droplet-action resize <droplet-id> --size s-2vcpu-4gb-amd --wait
```

Cost change: ~$12/mo → ~$28/mo.

## Rollback

Everything except the swap is contained. To remove Parallax cleanly:

```bash
ssh Jarvis 'systemctl stop parallax-api.service parallax-brief.timer
            systemctl disable parallax-api.service parallax-brief.timer
            rm /etc/systemd/system/parallax{.slice,-api.service,-brief.service,-brief.timer}
            systemctl daemon-reload
            rm -rf /root/parallax-markets /root/parallax-data /root/.parallax'

# Swap removal (optional — only if you also want to roll back the swap):
ssh Jarvis 'swapoff /swapfile && rm /swapfile && sed -i "/swapfile/d" /etc/fstab'
```
