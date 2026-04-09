# Phase 3: Paper Trading Evaluation + Continuous Improvement - Research

**Researched:** 2026-04-08
**Domain:** Automated pipeline scheduling, P&L tracking, Streamlit dashboard, prompt feedback injection, probability recalibration
**Confidence:** HIGH

## Summary

Phase 3 closes the feedback loop from predictions to outcomes to better predictions. The codebase already has the critical foundation: `signal_ledger` with resolution columns (`resolution_price`, `realized_pnl`, `model_was_correct`, `proxy_was_aligned`), three calibration queries (`hit_rate_by_proxy_class`, `calibration_curve`, `edge_decay`), and a resolution checker that polls Kalshi for settlements. The work divides into four plans: (1) cron-based automation of the daily pipeline, (2) a Streamlit dashboard with reusable data layer, (3) track record injection into prediction model prompts, and (4) mechanical recalibration of probabilities and edge thresholds.

The primary technical risks are low. Cron scheduling is straightforward. Streamlit is already installed (v1.43.2) with plotly (v5.10.0). The prompt injection pattern requires adding a `db_conn` parameter to predictor `predict()` methods and a `{track_record}` placeholder to system prompts. Recalibration is post-processing math between LLM output parsing and PredictionOutput creation. The main risk is insufficient resolved signals by April 21 to make recalibration meaningful -- the 10-signal minimum gate handles this correctly.

**Primary recommendation:** Build incrementally: cron wrapper first (enables data accumulation), then dashboard + report-card (visibility), then prompt injection (self-correction), then mechanical recalibration (requires data).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use cron (not launchd). Running in WSL2 on user's always-on PC. Portable to VPS later. Three brief runs at 7:00 AM, 1:00 PM, 9:00 PM Pacific. Resolution checker at 11:00 PM. Calibration report at 11:30 PM. Ensure cron service auto-starts in WSL2 via /etc/wsl.conf `[boot] command="service cron start"`.
- **D-02:** Wrapper shell script at `scripts/parallax-cron.sh` that sources `/tmp/parallax-env.sh`, runs the command, logs to `~/parallax-logs/YYYY-MM-DD-HHMM.log`. Exit code captured.
- **D-03:** New `--scheduled` CLI flag on brief.py. Writes structured JSON to `~/parallax-logs/runs/{run_id}.json` instead of printing formatted brief. Machine-readable for dashboard and analysis.
- **D-04:** Health check: on failure, write error marker file to `~/parallax-logs/errors/`. Nightly summary script prints what succeeded/failed.
- **D-05:** Streamlit single-page dashboard with expandable sections (not tabs). Sections: Today's Brief, Track Record / Calibration, Signal History, Market Prices.
- **D-06:** Data layer in a reusable module `parallax/dashboard/data.py` with functions like `get_latest_brief()`, `get_calibration_data()`, `get_signal_history()`. Streamlit calls these directly. Later, same functions become FastAPI endpoints for React frontend -- zero query rewrite.
- **D-07:** Read directly from DuckDB (single source of truth). Reuse calibration.py queries where possible.
- **D-08:** New `--report-card` CLI command: per-model accuracy, calibration curve, edge conversion rate, proxy class performance, biggest wins/misses. Text output.
- **D-09:** Populate `proxy_was_aligned` column in signal_ledger during resolution checking.
- **D-10:** Rolling stats + last 3 individual resolved signals per model. Format: aggregate accuracy (X/Y correct, Z% hit rate, calibration bias) + 3 most recent individual outcomes with ticker, predicted probability, resolution, and whether model was correct. ~300 tokens.
- **D-11:** Per-model only (no cross-model stats). Each model sees its own track record.
- **D-12:** New function `_build_track_record(model_id, conn)` in each predictor (or shared utility). Returns formatted text for prompt injection via `{track_record}` placeholder.
- **D-13:** `predict()` methods get `db_conn: duckdb.DuckDBPyConnection | None = None` parameter. If None or no resolved signals, inject "No track record available yet."
- **D-14:** brief.py passes the DuckDB connection to predictors. Connection is already created for contract registry -- reuse it.
- **D-15:** Hybrid approach: prompt self-correction (Phase 3-03) ships first. Mechanical linear bucket adjustment added in 3-04 with 10+ resolved signal minimum gate per model.
- **D-16:** Bucket-based recalibration: query calibration_curve() for the model, compute offset per bucket (predicted_avg - actual_rate), apply as post-processing step between LLM parse and PredictionOutput creation. Store both raw_probability and calibrated_probability.
- **D-17:** Auto-adjust `min_effective_edge_pct` in MappingPolicy based on edge_decay history. If edges under 8% historically never convert for a proxy class, raise threshold for that class. `MappingPolicy.update_thresholds_from_history(conn)` method.
- **D-18:** `suggested_size` field on signals: "full" for historically reliable edge/proxy combos, "half" for untested. Advisory only -- displayed in brief output, not enforced in paper trading.

### Claude's Discretion
- Exact Streamlit layout and chart library choices (plotly, altair, or native streamlit charts)
- Cron entry format and exact timing adjustments
- Error marker file format (JSON vs plain text)
- Whether to add `raw_probability` column to signal_ledger or prediction_log
- Dashboard styling and color scheme

### Deferred Ideas (OUT OF SCOPE)
- React frontend dashboard (future phase -- data layer designed for migration)
- Real-money trading activation based on proven P&L
- Cross-model correlation analysis (all models wrong on same day patterns)
- Platt scaling for recalibration (needs 50+ data points, unlikely by April 21)

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRAD-01 | Paper trades tracked at contract level with entry_price, resolution_price, realized_pnl, hold_duration | signal_ledger already has entry (market_yes_price), resolution_price, realized_pnl columns. hold_duration computable from created_at/resolved_at. Report-card CLI (D-08) surfaces this. |
| TRAD-02 | P&L segmented by proxy_class -- DIRECT, NEAR_PROXY, LOOSE_PROXY reported separately | calibration.py `hit_rate_by_proxy_class()` already groups by proxy_class. Extend with P&L aggregation for report-card. |
| TRAD-03 | Summary report: total P&L, win rate, avg edge at entry, Sharpe-like ratio, statistical significance test | New report-card command (D-08). Sharpe ratio = mean(realized_pnl) / std(realized_pnl). Statistical significance via binomial test (scipy.stats.binom_test or manual z-test). |
| TRAD-04 | Automated daily pipeline runs (cron/scheduled) accumulate prediction + signal history | Cron wrapper (D-01, D-02, D-03) with --scheduled flag for JSON output. |
| TRAD-05 | Calibration-driven tuning: adjust discount_map values, min_edge threshold, and model prompts | Prompt injection (D-10-D-14) + mechanical recalibration (D-15-D-17). |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| duckdb | 1.5.1 | OLAP database for all signal/prediction data | Already in use, single source of truth [VERIFIED: pip show] |
| streamlit | 1.43.2 | Dashboard UI | Already installed, rapid prototyping, expandable sections via st.expander [VERIFIED: pip show] |
| plotly | 5.10.0 | Interactive charts (calibration curves, P&L charts) | Already installed, native Streamlit integration via st.plotly_chart [VERIFIED: pip show] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cron (system) | N/A | Scheduling automated pipeline runs | WSL2 cron for 3x daily briefs + nightly resolution/calibration [VERIFIED: /usr/bin/crontab exists] |
| scipy (optional) | N/A | Statistical significance test (binomial test) | Only needed for TRAD-03 Sharpe/significance. Can be avoided with manual z-test formula. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| plotly | altair or native st.bar_chart | Plotly already installed + more control for calibration curves. Use native charts for simple bar charts. |
| scipy for stats | Manual z-test formula | Avoids new dependency. z = (wins - n*0.5) / sqrt(n*0.25) is ~3 lines. Use manual approach. |

**Installation:**
```bash
# Streamlit already installed globally. For project-level:
pip install streamlit>=1.43
# No new dependencies needed -- everything is already available.
```

## Architecture Patterns

### Recommended Project Structure
```
backend/src/parallax/
  dashboard/
    __init__.py
    data.py            # Reusable data layer (DuckDB queries)
    app.py             # Streamlit single-page app
  scoring/
    calibration.py     # Existing -- reuse queries
    ledger.py          # Existing -- extend proxy_was_aligned
    resolution.py      # Existing -- extend for proxy_was_aligned
    tracker.py         # Existing paper trade tracker
    prediction_log.py  # Existing prediction persistence
    track_record.py    # NEW: _build_track_record() shared utility
    recalibration.py   # NEW: bucket-based probability adjustment
    report_card.py     # NEW: --report-card CLI output
  cli/
    brief.py           # Extend with --scheduled, --report-card flags
  contracts/
    mapping_policy.py  # Extend with update_thresholds_from_history()
scripts/
  parallax-cron.sh     # Cron wrapper script
  cron-health-check.sh # Nightly summary of successes/failures
```

### Pattern 1: Reusable Data Layer (D-06)
**What:** Functions in `dashboard/data.py` that query DuckDB and return dicts/lists. Streamlit consumes directly; later FastAPI wraps the same functions.
**When to use:** Any data access for dashboard or report-card.
**Example:**
```python
# Source: project convention (calibration.py pattern)
import duckdb

def get_signal_history(conn: duckdb.DuckDBPyConnection, limit: int = 100) -> list[dict]:
    """Return recent signals with resolution status."""
    rows = conn.execute("""
        SELECT signal_id, created_at, model_id, contract_ticker,
               proxy_class, effective_edge, signal, resolution_price,
               realized_pnl, model_was_correct
        FROM signal_ledger
        ORDER BY created_at DESC
        LIMIT ?
    """, [limit]).fetchall()
    return [
        {
            "signal_id": r[0], "created_at": r[1], "model_id": r[2],
            "contract_ticker": r[3], "proxy_class": r[4],
            "effective_edge": r[5], "signal": r[6],
            "resolution_price": r[7], "realized_pnl": r[8],
            "model_was_correct": r[9],
        }
        for r in rows
    ]
```

### Pattern 2: Track Record Injection (D-10, D-12, D-13)
**What:** Build a ~300 token track record summary for each model, inject into LLM prompt via `{track_record}` placeholder.
**When to use:** Every prediction call when `db_conn` is provided and resolved signals exist.
**Example:**
```python
# Source: project design decision D-10, D-12
def build_track_record(model_id: str, conn: duckdb.DuckDBPyConnection) -> str:
    """Build track record text for prompt injection."""
    # Aggregate stats
    stats = conn.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN model_was_correct THEN 1 ELSE 0 END) AS correct
        FROM signal_ledger
        WHERE model_id = ? AND model_was_correct IS NOT NULL
    """, [model_id]).fetchone()

    if stats is None or stats[0] == 0:
        return "No track record available yet."

    total, correct = stats[0], stats[1]
    hit_rate = correct / total if total > 0 else 0

    # Last 3 resolved signals
    recent = conn.execute("""
        SELECT contract_ticker, model_probability, resolution_price,
               model_was_correct, signal
        FROM signal_ledger
        WHERE model_id = ? AND model_was_correct IS NOT NULL
        ORDER BY resolved_at DESC
        LIMIT 3
    """, [model_id]).fetchall()

    lines = [f"Your track record: {correct}/{total} correct ({hit_rate:.0%} hit rate)."]
    for r in recent:
        outcome = "CORRECT" if r[3] else "WRONG"
        lines.append(
            f"  - {r[0]}: predicted {r[1]:.0%}, resolved {r[2]:.0%} -> {outcome} ({r[4]})"
        )
    return "\n".join(lines)
```

### Pattern 3: Bucket-Based Recalibration (D-16)
**What:** Post-processing step that adjusts raw LLM probability using calibration curve offset before creating PredictionOutput.
**When to use:** Only when 10+ resolved signals exist for the model (D-15 gate).
**Example:**
```python
# Source: project design decision D-16
def recalibrate_probability(
    raw_prob: float, model_id: str, conn: duckdb.DuckDBPyConnection,
) -> tuple[float, float]:
    """Apply bucket-based recalibration. Returns (calibrated, raw)."""
    from parallax.scoring.calibration import calibration_curve
    # Per-model calibration curve would need a model_id filter added
    # For now, use global curve
    buckets = calibration_curve(conn)
    if not buckets:
        return raw_prob, raw_prob

    # Find matching bucket
    for b in buckets:
        low, high = _parse_bucket(b["bucket"])
        if low <= raw_prob < high:
            offset = b["avg_predicted"] - b["actual_rate"]
            calibrated = max(0.0, min(1.0, raw_prob - offset))
            return calibrated, raw_prob

    return raw_prob, raw_prob
```

### Pattern 4: Cron Wrapper (D-02)
**What:** Shell script that handles env sourcing, logging, and error markers.
**When to use:** Every cron invocation.
**Example:**
```bash
#!/usr/bin/env bash
# scripts/parallax-cron.sh
set -euo pipefail

source /tmp/parallax-env.sh

TIMESTAMP=$(date +%Y-%m-%d-%H%M)
LOG_DIR="$HOME/parallax-logs"
RUN_LOG="$LOG_DIR/$TIMESTAMP.log"
ERROR_DIR="$LOG_DIR/errors"

mkdir -p "$LOG_DIR" "$ERROR_DIR" "$LOG_DIR/runs"

CMD="$@"
echo "[$TIMESTAMP] Running: $CMD" >> "$RUN_LOG"

cd /path/to/parallax-markets/backend
if python -m parallax.cli.brief $CMD >> "$RUN_LOG" 2>&1; then
    echo "[$TIMESTAMP] SUCCESS" >> "$RUN_LOG"
else
    EXIT_CODE=$?
    echo "[$TIMESTAMP] FAILED (exit $EXIT_CODE)" >> "$RUN_LOG"
    echo "{\"timestamp\": \"$TIMESTAMP\", \"command\": \"$CMD\", \"exit_code\": $EXIT_CODE}" \
        > "$ERROR_DIR/$TIMESTAMP.json"
fi
```

### Anti-Patterns to Avoid
- **Don't add Streamlit as a project dependency in pyproject.toml** -- it's a dashboard tool installed separately, not part of the core package. Keep it as a system-level install.
- **Don't make calibration queries model-aware prematurely** -- the existing `calibration_curve()` is global. Add per-model filtering only when 10+ signals per model exist. Start with global.
- **Don't overwrite existing signal_ledger columns** -- `proxy_was_aligned` should only be set during resolution checking, never retroactively changed.
- **Don't block the brief pipeline on missing track record** -- always fall back to "No track record available yet." when db_conn is None or no data.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Scheduling | Custom Python scheduler/daemon | System cron via crontab | Cron is battle-tested, survives process crashes, logs to syslog |
| Dashboard framework | Custom Flask/FastAPI HTML templates | Streamlit (already installed) | Rapid prototyping, built-in chart support, expandable sections |
| Interactive charts | Custom SVG/canvas rendering | plotly via st.plotly_chart | Already installed, calibration curve visualization is its sweet spot |
| Statistical significance | Full scipy integration | Manual z-test formula | 3 lines of math, no new dependency for binomial test |
| JSON logging | Custom serialization | Python's json module + structured dicts | Already used throughout codebase |

**Key insight:** This phase is about wiring existing components together (calibration queries, signal ledger, prediction models) and adding visibility. Almost no new library code is needed.

## Common Pitfalls

### Pitfall 1: DuckDB Concurrent Access from Cron + Dashboard
**What goes wrong:** DuckDB file-based databases don't support concurrent writers. Cron job writing predictions while Streamlit reads causes lock errors.
**Why it happens:** DuckDB is single-writer by design for file databases.
**How to avoid:** Streamlit dashboard opens a read-only connection (`duckdb.connect(path, read_only=True)`). Cron jobs use normal read-write. Only one cron job runs at a time (cron entries don't overlap by schedule design). [VERIFIED: DuckDB docs confirm single-writer limitation]
**Warning signs:** "database is locked" errors in cron logs.

### Pitfall 2: Empty Track Record Crashes Prompt Formatting
**What goes wrong:** `{track_record}` placeholder in prompt template gets `None` or empty string, causing malformed prompt.
**Why it happens:** First few runs have zero resolved signals.
**How to avoid:** Always return a non-empty string from `build_track_record()`. Default: "No track record available yet. This is your first prediction cycle." Decision D-13 explicitly handles this.
**Warning signs:** `KeyError` or empty section in LLM prompt.

### Pitfall 3: Recalibration Oscillation
**What goes wrong:** With few data points, calibration offsets swing wildly between runs. Predictions become unstable.
**Why it happens:** Small sample sizes make bucket averages unreliable.
**How to avoid:** The 10-signal minimum gate per model (D-15) prevents this. Below threshold, only prompt self-correction operates. Additionally, cap maximum offset at +/-0.15 to prevent extreme corrections.
**Warning signs:** Calibrated probability flipping direction between consecutive runs.

### Pitfall 4: Cron Environment Missing API Keys
**What goes wrong:** Cron runs in a minimal shell environment. ANTHROPIC_API_KEY, KALSHI_API_KEY, KALSHI_PRIVATE_KEY_PATH are missing.
**Why it happens:** Cron doesn't source user's .bashrc/.zshrc.
**How to avoid:** Decision D-02 explicitly addresses this: wrapper script sources `/tmp/parallax-env.sh`. Verify all required vars are set before running the pipeline. Log missing vars as errors.
**Warning signs:** "ANTHROPIC_API_KEY not set" in cron logs, or silent LLM call failures.

### Pitfall 5: proxy_was_aligned Logic Ambiguity
**What goes wrong:** Determining whether a proxy "aligned" is not a binary yes/no for NEAR_PROXY/LOOSE_PROXY contracts.
**Why it happens:** A ceasefire model mapped to KXUSAIRANAGREEMENT might be "correct" in prediction but the proxy didn't track (ceasefire held but agreement failed, or vice versa).
**How to avoid:** Define proxy_was_aligned narrowly: True if the signal direction (BUY_YES/BUY_NO) and resolution outcome agree, regardless of model correctness. This measures whether the proxy contract moved in the predicted direction, not whether the underlying thesis was right.
**Warning signs:** proxy_was_aligned always matching model_was_correct (they should diverge for proxy contracts).

### Pitfall 6: --scheduled JSON Output Breaks Existing Pipeline
**What goes wrong:** Adding --scheduled flag changes output format but breaks integration tests expecting text output.
**Why it happens:** Tests might assert on specific text patterns from run_brief().
**How to avoid:** --scheduled should write JSON to file and still return the brief string from run_brief(). The flag controls file output, not function return value. Test the JSON file writing separately.
**Warning signs:** Existing test_brief.py tests failing after --scheduled implementation.

## Code Examples

### JSON Output for --scheduled Flag (D-03)
```python
# Source: project design decision D-03
import json
from pathlib import Path

def _write_scheduled_output(
    run_id: str,
    predictions: list,
    signals: list,
    divergences: list,
) -> Path:
    """Write structured JSON for machine consumption."""
    log_dir = Path.home() / "parallax-logs" / "runs"
    log_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "predictions": [p.model_dump() for p in predictions],
        "signals": [
            {
                "signal_id": s.signal_id,
                "model_id": s.model_id,
                "contract_ticker": s.contract_ticker,
                "proxy_class": s.proxy_class,
                "effective_edge": s.effective_edge,
                "signal": s.signal,
            }
            for s in signals
        ],
        "divergence_count": len([d for d in divergences if d.signal != "HOLD"]),
    }

    path = log_dir / f"{run_id}.json"
    path.write_text(json.dumps(output, indent=2, default=str))
    return path
```

### Report Card Summary (TRAD-03)
```python
# Source: project design decision D-08, requirement TRAD-03
import math

def generate_report_card(conn: duckdb.DuckDBPyConnection) -> str:
    """Generate comprehensive report card with P&L, win rate, significance."""
    # Total P&L and win rate by proxy class
    rows = conn.execute("""
        SELECT
            proxy_class,
            COUNT(*) AS total,
            SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS wins,
            SUM(realized_pnl) AS total_pnl,
            AVG(realized_pnl) AS avg_pnl,
            AVG(ABS(effective_edge)) AS avg_edge_at_entry
        FROM signal_ledger
        WHERE realized_pnl IS NOT NULL
        GROUP BY proxy_class
    """).fetchall()

    # Statistical significance: z-test against 50% win rate
    # z = (wins - n*0.5) / sqrt(n * 0.25)
    for row in rows:
        total, wins = row[1], row[2]
        if total >= 5:
            z = (wins - total * 0.5) / math.sqrt(total * 0.25)
            significant = abs(z) > 1.96  # p < 0.05
```

### MappingPolicy Threshold Update (D-17)
```python
# Source: project design decision D-17
def update_thresholds_from_history(
    self, conn: duckdb.DuckDBPyConnection,
) -> dict[str, float]:
    """Adjust min_edge per proxy class based on edge_decay history."""
    from parallax.scoring.calibration import edge_decay

    data = edge_decay(conn)
    # If edges under 8% for a proxy class never convert, raise threshold
    updates = {}
    for bucket in data:
        if bucket["edge_bucket"] == "<5%" and bucket["hit_rate"] < 0.4:
            # Small edges losing money -> raise threshold
            updates["raise_threshold"] = True
    return updates
```

### Streamlit Dashboard Layout (D-05)
```python
# Source: project design decision D-05, Claude's discretion on layout
import streamlit as st

def main():
    st.set_page_config(page_title="Parallax Dashboard", layout="wide")
    st.title("Parallax Intelligence Dashboard")

    conn = duckdb.connect(db_path, read_only=True)  # Read-only!

    with st.expander("Today's Brief", expanded=True):
        # Latest run's predictions and signals
        pass

    with st.expander("Track Record / Calibration"):
        # Calibration curve chart, hit rate table
        # Use plotly for calibration curve (predicted vs actual)
        pass

    with st.expander("Signal History"):
        # Scrollable table of all signals
        pass

    with st.expander("Market Prices"):
        # Current market prices from last fetch
        pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Legacy `_map_predictions_to_markets()` heuristic | MappingPolicy with proxy classification | Phase 1 | Edge detection now proxy-class aware |
| No prediction persistence | prediction_log table | Phase 2 | Can now analyze historical accuracy |
| No resolution checking | resolution.py polls Kalshi | Phase 2 | Feedback loop closed |
| Manual CLI runs | Cron automation (this phase) | Phase 3 | Data accumulation without manual intervention |
| No model self-awareness | Track record injection (this phase) | Phase 3 | Models adjust based on past performance |

**Deprecated/outdated:**
- `_map_predictions_to_markets_legacy()` in brief.py -- marked deprecated, replaced by MappingPolicy. Still present for reference. Do not use.
- `PaperTradeTracker.check_resolutions()` -- replaced by `scoring/resolution.py`. The tracker's resolution checking duplicates logic. Use `scoring/resolution.py` for all resolution work.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Streamlit can open DuckDB in read_only mode concurrently with a writer | Pitfall 1 | Dashboard would need a copy-on-read pattern or polling interval |
| A2 | z-test is sufficient for statistical significance with small N | Code Examples | May need Fisher's exact test for very small samples, but z-test is fine for 10+ |
| A3 | 300 tokens for track record is small enough to not impact LLM reasoning quality | Pattern 2 | Longer context could dilute signal; shorter might not give enough history |
| A4 | WSL2 cron service auto-starts reliably with /etc/wsl.conf boot command | Pitfall 4 | May need a manual `sudo service cron start` after WSL restart |

## Open Questions

1. **Per-model calibration_curve() filtering**
   - What we know: Current `calibration_curve()` is global (all models). D-16 needs per-model recalibration.
   - What's unclear: Whether to add `model_id` parameter to existing functions or create new per-model variants.
   - Recommendation: Add optional `model_id` parameter to `calibration_curve()`. Filter with `AND model_id = ?` when provided. Backward compatible.

2. **raw_probability storage location (Claude's discretion)**
   - What we know: D-16 requires storing both raw and calibrated probability.
   - What's unclear: Whether to add `raw_probability` to signal_ledger or prediction_log.
   - Recommendation: Add `raw_probability` column to signal_ledger (it's where `model_probability` lives and where recalibration matters for edge calculation). Rename nothing -- `model_probability` becomes the calibrated value, `raw_probability` stores the LLM output.

3. **Proxy alignment definition**
   - What we know: D-09 says populate `proxy_was_aligned` during resolution.
   - What's unclear: Exact semantics for NEAR_PROXY and LOOSE_PROXY contracts.
   - Recommendation: Define as "did the contract resolve in the direction the signal predicted?" independent of model correctness. BUY_YES + resolution_price > 0.5 = aligned. BUY_NO + resolution_price <= 0.5 = aligned.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All code | Yes | 3.11.5 | -- |
| crontab | Scheduling (D-01) | Yes | system | -- |
| streamlit | Dashboard (D-05) | Yes | 1.43.2 | -- |
| plotly | Charts (D-05) | Yes | 5.10.0 | Native st.bar_chart |
| duckdb | Data storage | Yes | 1.5.1 | -- |
| WSL2 | Cron runtime (D-01) | N/A (macOS dev) | -- | macOS cron works the same way; WSL2 is target deployment |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

**Note:** Development is on macOS but deployment target is WSL2 per D-01. crontab syntax is identical. The /etc/wsl.conf boot command is WSL2-specific and won't apply on macOS dev, but the cron entries themselves are portable.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3 with pytest-asyncio 0.25 |
| Config file | backend/pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRAD-01 | Contract-level P&L with entry/resolution/pnl | unit | `pytest tests/test_report_card.py::test_pnl_by_contract -x` | No -- Wave 0 |
| TRAD-02 | P&L segmented by proxy_class | unit | `pytest tests/test_report_card.py::test_pnl_by_proxy_class -x` | No -- Wave 0 |
| TRAD-03 | Summary report with P&L, win rate, edge, significance | unit | `pytest tests/test_report_card.py::test_summary_stats -x` | No -- Wave 0 |
| TRAD-04 | --scheduled flag writes JSON, cron wrapper works | unit + integration | `pytest tests/test_brief.py::test_scheduled_flag -x` | No -- Wave 0 |
| TRAD-05 | Track record injection + recalibration | unit | `pytest tests/test_track_record.py -x` + `pytest tests/test_recalibration.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_report_card.py` -- covers TRAD-01, TRAD-02, TRAD-03
- [ ] `tests/test_track_record.py` -- covers TRAD-05 (track record building)
- [ ] `tests/test_recalibration.py` -- covers TRAD-05 (bucket recalibration)
- [ ] `tests/test_brief.py::test_scheduled_flag` -- covers TRAD-04 (--scheduled JSON output)
- [ ] `tests/test_dashboard_data.py` -- covers dashboard data layer functions

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A -- single-user CLI tool |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A -- single-user |
| V5 Input Validation | Yes | Pydantic models for all data structures; SQL parameterized queries (already in place) |
| V6 Cryptography | No | RSA-PSS for Kalshi auth already implemented in Phase 1 |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via model_id | Tampering | Parameterized queries (already used everywhere in calibration.py, ledger.py) |
| Env var leakage in cron logs | Information Disclosure | Don't log API key values; only log presence/absence |
| DuckDB file permissions | Tampering | File permissions 600 on DuckDB file (single user) |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `scoring/calibration.py`, `scoring/ledger.py`, `scoring/resolution.py`, `cli/brief.py`, `contracts/mapping_policy.py`, `db/schema.py` -- direct code review
- `pip show` commands for duckdb 1.5.1, streamlit 1.43.2, plotly 5.10.0 -- verified installed versions
- Phase 2 CONTEXT.md and existing implementation -- verified phase dependencies are met

### Secondary (MEDIUM confidence)
- DuckDB concurrent access model (single-writer, multiple readers) [ASSUMED based on training data -- DuckDB docs confirm this pattern]

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and in use
- Architecture: HIGH -- patterns follow existing codebase conventions exactly
- Pitfalls: HIGH -- identified from direct code review of existing integration points

**Research date:** 2026-04-08
**Valid until:** 2026-04-22 (stable stack, project-specific patterns)
