# KalshiBench Calibration Audit Harness

> **What this is:** a small, self-contained harness that takes a frozen LLM, scores how
> *(mis)calibrated* its stated confidence is on a public set of already-resolved questions, fits a
> recalibration map on held-out data, and measures whether recalibration **actually beats raw model
> confidence** out-of-fold. It produces a reliability diagram, a Brier/ECE table, and a verdict.
>
> **Why it exists:** Parallax began as an LLM prediction-market trader. The honest finding from
> months of research + the project's own logs is that **there is no demonstrated trading edge** —
> LLMs don't beat liquid markets, and execution (not prediction) is the binding constraint
> (see `PROFITABILITY-STRATEGY-2026-06.md`). What *is* salvageable and genuinely reusable is the
> project's **forecast → resolve → score → recalibrate** loop. This harness is the cheapest proof
> of that: it points the loop at a public resolved set instead of a live market.

## The question it answers

> *Does fitting a recalibration map on a held-out slice measurably beat raw model confidence
> (lower Brier / ECE)?*

It compares four maps under identical grouped, out-of-fold cross-validation:

| Method | What it is |
|---|---|
| `raw` | the model's stated probability (baseline) |
| `bucket_offset` | **Parallax's own method** (`scoring/recalibration.py`), reproduced as fit/apply |
| `isotonic` | standard monotone nonparametric calibration (sklearn) |
| `platt` | logistic (sigmoid) calibration in logit space |

A key thing it checks: whether the project's bucket-offset map is **monotonic**. A non-monotone map
re-orders forecasts (depresses AUC) — a structural defect that the standard calibrators avoid by
construction. Catching that is part of the value.

## How to run

```bash
cd backend
pip install -e ".[bench]"          # numpy, scikit-learn, matplotlib, pandas, huggingface_hub
export ANTHROPIC_API_KEY=...        # forecasts cost ~$10 for all 3 models on the full 1,531

# All three frontier models on the full KalshiBench-v2 (1,531 resolved questions):
python -m parallax.cli.kalshibench --models haiku,sonnet,opus

# Cheap smoke test (one model, 60 questions):
python -m parallax.cli.kalshibench --models haiku --limit 60

# Re-score from cached forecasts without spending on the API:
python -m parallax.cli.kalshibench --models haiku,sonnet,opus --no-llm
```

Outputs land in `docs/reports/kalshibench-<date>/`: `REPORT.md` (table + verdict + caveats),
`reliability.png` (raw vs recalibrated curves + sharpness), `results.json` (raw metrics).
Forecasts are checkpointed to `backend/data/bench/forecasts_<model>.jsonl` and reused on re-runs.

## Methodology (and its honest limits)

- **Data:** KalshiBench-v2 (`2084Collective/kalshibench-v2` on HuggingFace) — 1,531 resolved binary
  Kalshi questions with ground-truth outcomes. It ships **no forecasts**, so the harness generates
  them by asking each model for a single `P(YES)` via a forced tool call (works across all current
  Claude models; no chain-of-thought, for cost and parse reliability).
- **Out-of-fold evaluation:** recalibration maps are fit on TRAIN folds and applied to held-out
  folds via **grouped 5-fold CV** (grouped by `series_ticker`, so an event's rows never split across
  train/test). In-sample recalibration trivially "wins"; only out-of-fold results are meaningful.
- **Metrics:** Brier (primary — a proper scoring rule), ECE + adaptive/equal-mass ACE
  (binning-robust), log-loss, AUC (discrimination; a drop flags a non-monotone map). Paired
  bootstrap 95% CIs on every (method − raw) delta so improvements aren't over-claimed.

## Extended analyses (v2)

Beyond the raw-vs-recalibrated calibration table, the harness now reports:

- **Selective prediction / act-or-escalate** — the other half of the proof-of-value question
  ("auto-handle more at a fixed error rate?"). Two views: (A) an operating point with the
  confidence threshold fit on TRAIN and scored OOF; (B) honesty at a nominal confidence bar.
  Honest finding: recalibration buys **honesty** (realized error ≤ promised at a nominal bar) but
  **not more volume** at a fixed bar, and it does **not** improve selective-prediction *ranking*
  (AURC ≈ flat, raw marginally better) — calibration ≠ discrimination.
- **Cluster (event) bootstrap** for the headline CIs (resamples `series_ticker`, not rows — the
  unit that respects within-event dependence), plus **Brier Skill Score** vs base-rate climatology.
- **Per-category breakdown** (n≥50, rest pooled) — recalibration gains concentrate in
  poorly-calibrated domains (Crypto, Companies, Mentions); well-calibrated ones (Sports, all of
  Opus) gain ~nothing.
- **Temporal stability** (fit on earliest 60% by close_time, score latest 40%) — a key tempering
  caveat: recalibration maps **do not transfer cleanly forward in time** here, so the random-CV
  gains are an upper bound on a fixed deployed map. This is an intra-distribution recency probe,
  not prospective validation.

Methodology note: the two cross-checking reviewers (Codex, Gemini) disagreed on the selective
primary view; both are reported and neither is over-claimed (see `REPORT.md`).

### ⚠️ The dominant caveat: leakage

Every KalshiBench question resolved in **2025**, within the knowledge cutoff of these models. A model
may therefore **recall** an outcome rather than forecast it. So these results measure **whether
recalibration improves the calibration of the models' stated confidence on these outputs** — they are
**not** a forecasting-skill claim on unknown futures. The recalibration question is still valid
(fitting a map and beating raw confidence out-of-fold is a real test); external validity to live
forecasting is not established here. The generated `REPORT.md` states this up front.

Other honest limits: ECE is a biased, binning-dependent estimator (Brier is primary); model rows
share the same questions and are **not independent** (per-model results are primary); the no-CoT
elicitation is a fixed, reproducible protocol, not necessarily each model's best calibration.

## Code map

| File | Role |
|---|---|
| `scoring/calibration_metrics.py` | pure-numpy Brier / log-loss / ECE / ACE / AUC / reliability / decomposition / bootstrap |
| `scoring/recalibrators.py` | fit/apply maps: bucket-offset (the project's), isotonic, Platt + monotonicity checks |
| `scoring/recalibration.py` | the project's *original* live recalibrator (reused, not duplicated) |
| `bench/kalshibench.py` | dataset loader (cached parquet) |
| `bench/forecast.py` | async, checkpointed, budget-tracked multi-model forecast generation |
| `cli/kalshibench.py` | orchestrator: forecast → grouped OOF recalibrate → metrics → diagram → report |

Tests: `tests/test_calibration_metrics.py`, `tests/test_recalibrators.py`, `tests/test_bench_forecast.py`.

For the latest run's numbers and verdict, see the newest `docs/reports/kalshibench-*/REPORT.md`.
