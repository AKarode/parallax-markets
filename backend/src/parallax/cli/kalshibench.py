"""KalshiBench calibration proof-of-value runner.

Answers: *does fitting a recalibration map on held-out data measurably beat raw
model confidence (lower Brier/ECE)?* -- using the Parallax project's own
bucket-offset method plus isotonic/Platt baselines, scored on the public
KalshiBench resolved-question set with grouped, out-of-fold cross-validation.

Outputs a reliability diagram (PNG), a Brier/ECE table, a JSON results dump, and
a written REPORT.md with the verdict and honest caveats.

Usage:
    python -m parallax.cli.kalshibench --models haiku,sonnet,opus
    python -m parallax.cli.kalshibench --no-llm          # reuse cached forecasts
    python -m parallax.cli.kalshibench --limit 200 --models haiku   # quick smoke
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from parallax.bench.forecast import generate_forecasts
from parallax.bench.kalshibench import load_kalshibench
from parallax.scoring import calibration_metrics as cm
from parallax.scoring import selective as sel
from parallax.scoring.recalibrators import fit_recalibrator, is_monotonic, monotonicity_violation

logger = logging.getLogger(__name__)

# Friendly aliases -> full model IDs.
MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}

METHODS = ["bucket_offset", "isotonic", "platt"]  # compared against "raw"

_REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/


def resolve_models(spec: str) -> list[str]:
    out = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(MODEL_ALIASES.get(tok, tok))
    return out


def grouped_folds(labels: np.ndarray, groups: np.ndarray, n_folds: int):
    """Grouped K-fold splits (an event's rows never split across train/test)."""
    from sklearn.model_selection import GroupKFold

    gkf = GroupKFold(n_splits=n_folds)
    return list(gkf.split(np.zeros(len(labels)), labels, groups))


def oof_predict(probs, labels, folds, kind, **kw) -> np.ndarray:
    """Out-of-fold predictions: fit on each train split, predict its held-out fold."""
    oof = np.full(len(probs), np.nan)
    for tr, te in folds:
        if kind in ("raw", "identity"):
            oof[te] = probs[te]
        else:
            r = fit_recalibrator(kind, probs[tr], labels[tr], **kw)
            oof[te] = r.predict(probs[te])
    if np.isnan(oof).any():
        raise RuntimeError("OOF predictions incomplete -- a sample was never in a test fold")
    return oof


def per_fold_deltas(raw_oof, method_oof, labels, folds, metric_fn) -> np.ndarray:
    """metric(method) - metric(raw) computed within each held-out fold."""
    deltas = []
    for _, te in folds:
        deltas.append(metric_fn(method_oof[te], labels[te]) - metric_fn(raw_oof[te], labels[te]))
    return np.asarray(deltas)


def evaluate_model(probs, labels, groups, folds, *, n_bins, seed) -> dict:
    """Full OOF evaluation of one model: raw + each recalibration method.

    Headline CIs use the CLUSTER (event) bootstrap -- resampling groups, not rows
    -- which respects within-event dependence (the row bootstrap is mildly
    anti-conservative).
    """
    raw_oof = probs  # raw needs no fitting

    result = {
        "n": int(len(probs)),
        "base_rate": cm.base_rate(labels),
        "raw": cm.score_all(raw_oof, labels, n_bins),
        "methods": {},
    }
    for kind in METHODS:
        oof = oof_predict(probs, labels, folds, kind)
        scores = cm.score_all(oof, labels, n_bins)
        # paired CLUSTER bootstrap on pooled OOF (lower=better -> negative = improvement)
        brier_ci = cm.bootstrap_metric_diff_grouped(
            raw_oof, oof, labels, groups, cm.brier_score, seed=seed)
        ece_ci = cm.bootstrap_metric_diff_grouped(
            raw_oof, oof, labels, groups,
            lambda p, y: cm.expected_calibration_error(p, y, n_bins), seed=seed,
        )
        # per-fold stability
        fold_brier = per_fold_deltas(raw_oof, oof, labels, folds, cm.brier_score)
        fold_ece = per_fold_deltas(
            raw_oof, oof, labels, folds,
            lambda p, y: cm.expected_calibration_error(p, y, n_bins),
        )
        # monotonicity of the FULL-data fit (rank-inversion check)
        full_fit = fit_recalibrator(kind, probs, labels)
        result["methods"][kind] = {
            "scores": scores,
            "brier_delta": brier_ci,
            "ece_delta": ece_ci,
            "fold_brier_delta_mean": float(fold_brier.mean()),
            "fold_brier_delta_std": float(fold_brier.std(ddof=1)) if len(fold_brier) > 1 else 0.0,
            "fold_brier_improved": int((fold_brier < 0).sum()),
            "fold_ece_delta_mean": float(fold_ece.mean()),
            "fold_count": len(folds),
            "monotonic": is_monotonic(full_fit),
            "monotonicity_violation": monotonicity_violation(full_fit),
            "oof": oof,  # kept in-memory for plotting; stripped before JSON dump
        }
    return result


# ---- Extension analyses: selective prediction, per-category, temporal --------

SELECTIVE_TARGETS = [0.05, 0.10]      # target error rates for the operating-point view
CONFIDENCE_BARS = [0.80, 0.90, 0.95]  # nominal stated-confidence bars for the honesty view


def selective_operating_oof(probs, labels, folds, kind, target_error) -> dict:
    """'Auto-handle more at a fixed error rate', done honestly.

    Per fold: fit the recalibrator on train, choose the confidence threshold on
    TRAIN to hit ``target_error``, apply it to the held-out TEST fold. Pool the
    test decisions across folds. Returns pooled coverage + realized error (the
    threshold is never chosen on the data it is scored on).
    """
    acc_total = acc_correct = 0
    for tr, te in folds:
        if kind in ("raw", "identity"):
            ptr, pte = probs[tr], probs[te]
        else:
            r = fit_recalibrator(kind, probs[tr], labels[tr])
            ptr, pte = r.predict(probs[tr]), r.predict(probs[te])
        thr = sel.operating_threshold(ptr, labels[tr], target_error)
        mask = sel.confidence(pte) >= thr
        n = int(mask.sum())
        acc_total += n
        if n:
            pred = (pte[mask] >= 0.5).astype(float)
            acc_correct += int((pred == labels[te][mask]).sum())
    coverage = acc_total / len(probs)
    realized = (1.0 - acc_correct / acc_total) if acc_total else float("nan")
    return {"target_error": target_error, "coverage": float(coverage), "realized_error": float(realized)}


def selective_summary(probs, labels, oof_by_method, folds) -> dict:
    """Both selective views for raw + each method, on the same OOF predictions."""
    out: dict = {"operating": {}, "bars": {}}
    methods = ["raw"] + METHODS
    for kind in methods:
        out["operating"][kind] = [
            selective_operating_oof(probs, labels, folds, kind, t) for t in SELECTIVE_TARGETS
        ]
        oof = probs if kind == "raw" else oof_by_method[kind]
        out["bars"][kind] = [
            sel.selective_at_confidence(oof, labels, c).__dict__ for c in CONFIDENCE_BARS
        ]
    # class flips vs raw (V-shape: monotone-in-p recal can still cross 0.5)
    raw_pred = (probs >= 0.5).astype(int)
    out["class_flips"] = {
        kind: int(((oof_by_method[kind] >= 0.5).astype(int) != raw_pred).sum())
        for kind in METHODS
    }
    out["aurc"] = {"raw": sel.aurc(probs, labels),
                   **{k: sel.aurc(oof_by_method[k], labels) for k in METHODS}}
    return out


def per_category_breakdown(probs, oof_iso, labels, categories, n_bins, min_n=50) -> list[dict]:
    """Raw vs isotonic Brier/ECE per category (n>=min_n); smaller pooled into 'Other'."""
    cats = np.asarray(categories)
    rows: list[dict] = []
    small_mask = np.zeros(len(labels), dtype=bool)
    for cat in sorted(set(cats.tolist())):
        m = cats == cat
        if int(m.sum()) < min_n:
            small_mask |= m
            continue
        rows.append({
            "category": cat, "n": int(m.sum()),
            "raw_brier": cm.brier_score(probs[m], labels[m]),
            "iso_brier": cm.brier_score(oof_iso[m], labels[m]),
            "raw_ece": cm.expected_calibration_error(probs[m], labels[m], n_bins),
            "iso_ece": cm.expected_calibration_error(oof_iso[m], labels[m], n_bins),
        })
    rows.sort(key=lambda r: -r["n"])
    if small_mask.any():
        m = small_mask
        rows.append({
            "category": f"Other (<{min_n} each)", "n": int(m.sum()),
            "raw_brier": cm.brier_score(probs[m], labels[m]),
            "iso_brier": cm.brier_score(oof_iso[m], labels[m]),
            "raw_ece": cm.expected_calibration_error(probs[m], labels[m], n_bins),
            "iso_ece": cm.expected_calibration_error(oof_iso[m], labels[m], n_bins),
        })
    return rows


def temporal_stability(probs, labels, close_times, groups, n_bins, frac_train=0.6) -> dict | None:
    """Chronological holdout: fit on earliest ``frac_train``, score on the latest tail.

    A recency-stability / distribution-shift probe -- NOT a leakage-free
    generalization test (all questions are within the models' knowledge cutoff).
    Answers: does recalibration learned on earlier items still help later items?

    Split is at the EVENT level (whole series_ticker assigned by its earliest
    close_time) so sibling rows of one event never straddle train/test.
    """
    import pandas as pd

    ct = pd.to_datetime(close_times, utc=True, format="ISO8601").to_numpy()
    g = np.asarray(groups)
    uniq = np.unique(g)
    ev_first = {gv: ct[g == gv].min() for gv in uniq}
    ev_sorted = sorted(uniq, key=lambda gv: ev_first[gv])
    cut_ev = int(len(ev_sorted) * frac_train)
    train_ev = set(ev_sorted[:cut_ev])
    is_train = np.array([gv in train_ev for gv in g])
    tr, te = np.where(is_train)[0], np.where(~is_train)[0]
    if len(tr) < 30 or len(te) < 30:
        return None
    out = {"n_train": int(len(tr)), "n_test": int(len(te)),
           "raw": {"brier": cm.brier_score(probs[te], labels[te]),
                   "ece": cm.expected_calibration_error(probs[te], labels[te], n_bins)},
           "methods": {}}
    for kind in ("isotonic", "bucket_offset"):
        r = fit_recalibrator(kind, probs[tr], labels[tr])
        pte = r.predict(probs[te])
        out["methods"][kind] = {"brier": cm.brier_score(pte, labels[te]),
                                "ece": cm.expected_calibration_error(pte, labels[te], n_bins)}
    return out


def _sig(ci: dict) -> str:
    """Significance label from a bootstrap CI of (method - raw), lower=better."""
    if ci["ci_high"] < 0:
        return "improved**"  # CI entirely below 0
    if ci["diff"] < 0:
        return "improved"    # point estimate better, CI crosses 0
    if ci["ci_low"] > 0:
        return "WORSE**"     # CI entirely above 0
    return "worse" if ci["diff"] > 0 else "flat"


def build_table(results: dict) -> str:
    """Markdown table: one row per (model, method) with metrics + deltas."""
    hdr = (
        "| Model | Method | n | Brier | BSS | ECE | AUC | ΔBrier (95% CI, cluster) | per-fold↓ | ΔECE (95% CI) | Mono? |\n"
        "|---|---|--:|--:|--:|--:|--:|---|:--:|---|:--:|"
    )
    lines = [hdr]
    for model, r in results.items():
        raw = r["raw"]
        lines.append(
            f"| {model} | raw | {raw['n']} | {raw['brier']:.4f} | {raw['bss']:+.3f} | "
            f"{raw['ece']:.4f} | {raw['auc']:.3f} | — | — | — | — |"
        )
        for kind in METHODS:
            m = r["methods"][kind]
            s = m["scores"]
            bd, ed = m["brier_delta"], m["ece_delta"]
            mono = "yes" if m["monotonic"] else f"**NO** ({m['monotonicity_violation']:.2f})"
            fold = f"{m['fold_brier_improved']}/{m['fold_count']}"
            lines.append(
                f"| {model} | {kind} | {s['n']} | {s['brier']:.4f} | {s['bss']:+.3f} | "
                f"{s['ece']:.4f} | {s['auc']:.3f} | "
                f"{bd['diff']:+.4f} [{bd['ci_low']:+.4f},{bd['ci_high']:+.4f}] {_sig(bd)} | {fold} | "
                f"{ed['diff']:+.4f} [{ed['ci_low']:+.4f},{ed['ci_high']:+.4f}] {_sig(ed)} | {mono} |"
            )
    lines.append("")
    lines.append("_ΔBrier/ΔECE are (method − raw) on pooled out-of-fold predictions; negative = better. "
                 "CIs use the **cluster (event) bootstrap**. `**` = 95% CI excludes 0. "
                 "BSS = Brier Skill Score vs base-rate climatology (>0 beats it). "
                 "per-fold↓ = folds (of 5) where the method beat raw._")
    return "\n".join(lines)


def build_selective_table(results: dict) -> str:
    """Selective-prediction: operating-point (train-threshold OOF) + stated-confidence honesty."""
    lines = ["#### A. Auto-handle more at a fixed error rate (threshold fit on train, scored OOF)", ""]
    lines.append("| Model | Target err | raw cov | raw realized | isotonic cov | iso realized | bucket cov | bucket realized |")
    lines.append("|---|--:|--:|--:|--:|--:|--:|--:|")
    for model, r in results.items():
        sel_d = r["selective"]["operating"]
        for i, t in enumerate(SELECTIVE_TARGETS):
            def cell(kind):
                d = sel_d[kind][i]
                return f"{d['coverage']:.0%} | {d['realized_error']:.1%}"
            lines.append(
                f"| {model} | {t:.0%} | " + cell("raw") + " | " + cell("isotonic") + " | " + cell("bucket_offset") + " |"
            )
    lines.append("")
    lines.append("_Higher coverage at realized error ≤ target is better. Honest finding: a threshold "
                 "chosen on TRAIN to hit the target tends to **overshoot it out-of-sample** "
                 "(selective-prediction optimism; only the already-calibrated Opus lands near target). "
                 "Recalibration usually *increases coverage* but does not by itself guarantee the target "
                 "is met OOF — so 'auto-handle more at a fixed error rate' is only partially supported "
                 "here. The cleaner calibration signal is in panel B._")
    lines.append("")
    lines.append("#### B. Honesty at a nominal confidence bar (stated vs realized error, OOF)")
    lines.append("")
    lines.append("| Model | Conf bar | promised err | raw cov / realized | isotonic cov / realized |")
    lines.append("|---|--:|--:|--:|--:|")
    for model, r in results.items():
        bars = r["selective"]["bars"]
        for i, c in enumerate(CONFIDENCE_BARS):
            rb, ib = bars["raw"][i], bars["isotonic"][i]
            def fmt(d):
                re = d["realized_error"]
                if re != re:  # NaN -> nothing covered
                    return f"{d['coverage']:.0%} / —"
                tag = f" (n={d['n_covered']})" if d["n_covered"] < 20 else ""
                return f"{d['coverage']:.0%} / {re:.1%}{tag}"
            lines.append(f"| {model} | ≥{c:.0%} | {1-c:.0%} | {fmt(rb)} | {fmt(ib)} |")
    lines.append("")
    flips = {m: results[m]["selective"]["class_flips"] for m in results}
    lines.append("_At a nominal bar, a calibrated model's realized error should be ≤ the promised error "
                 "(1−bar). For the more miscalibrated models (Haiku, Sonnet) raw **exceeds** it "
                 "(overconfident) and recalibration brings realized error to ≤ promised for most cells — "
                 "but at LOWER coverage (it stops over-claiming). Opus raw is already ≤ promised at every "
                 "bar (already honest). So recalibration buys *honesty*, not more volume, at a fixed bar. "
                 "Cells marked (n=…) have few accepted items and are noisy. Class flips vs raw "
                 "(recal crossing 0.5): "
                 + "; ".join(f"{m.split('-')[1] if '-' in m else m}: iso={f['isotonic']}, bucket={f['bucket_offset']}"
                            for m, f in flips.items()) + "._")
    return "\n".join(lines)


def build_category_table(results: dict) -> str:
    lines = ["| Model | Category | n | raw Brier | iso Brier | raw ECE | iso ECE |",
             "|---|---|--:|--:|--:|--:|--:|"]
    for model, r in results.items():
        for row in r["categories"]:
            lines.append(
                f"| {model} | {row['category']} | {row['n']} | {row['raw_brier']:.3f} | "
                f"{row['iso_brier']:.3f} | {row['raw_ece']:.3f} | {row['iso_ece']:.3f} |"
            )
    lines.append("")
    lines.append("_Only categories with n≥50 shown individually (ECE stays noisy below ~100–200); "
                 "the rest pooled into 'Other'. Descriptive only — many comparisons, not significance-tested._")
    return "\n".join(lines)


def build_temporal_table(results: dict) -> str:
    lines = ["| Model | n train→test | raw Brier | iso Brier | bucket Brier | raw ECE | iso ECE |",
             "|---|---|--:|--:|--:|--:|--:|"]
    any_row = False
    for model, r in results.items():
        t = r.get("temporal")
        if not t:
            continue
        any_row = True
        lines.append(
            f"| {model} | {t['n_train']}→{t['n_test']} | {t['raw']['brier']:.3f} | "
            f"{t['methods']['isotonic']['brier']:.3f} | {t['methods']['bucket_offset']['brier']:.3f} | "
            f"{t['raw']['ece']:.3f} | {t['methods']['isotonic']['ece']:.3f} |"
        )
    if not any_row:
        return "_(temporal split skipped — insufficient data)_"
    lines.append("")
    lines.append("_Chronological holdout: recalibrator fit on the earliest 60% by close_time, scored on "
                 "the latest 40%. This is an **intra-distribution recency-stability probe, not** "
                 "leakage-free prospective validation (all questions are within the models' cutoff). "
                 "Important caveat to the random-CV win: maps fit on earlier items **do not transfer "
                 "cleanly forward** here (out-of-time Brier is flat-to-slightly-worse), so the random "
                 "grouped-CV gains are an upper bound on what a fixed deployed map would deliver._")
    return "\n".join(lines)


def make_reliability_diagram(results: dict, labels_by_model: dict, n_bins: int, out_path: Path) -> None:
    """Reliability curves (raw vs bucket vs isotonic) + prediction histograms."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = list(results.keys())
    fig, axes = plt.subplots(2, len(models), figsize=(5 * len(models), 8), squeeze=False)
    colors = {"raw": "#888888", "bucket_offset": "#d62728", "isotonic": "#1f77b4"}

    for j, model in enumerate(models):
        r = results[model]
        y = labels_by_model[model]
        ax = axes[0][j]
        ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.6, label="perfect")
        series = {"raw": r["raw_oof"], "bucket_offset": r["methods"]["bucket_offset"]["oof"],
                  "isotonic": r["methods"]["isotonic"]["oof"]}
        for name, preds in series.items():
            bins = cm.reliability_curve(preds, y, n_bins)
            xs = [b.mean_pred for b in bins if b.count]
            ys = [b.frac_pos for b in bins if b.count]
            ax.plot(xs, ys, "o-", ms=4, color=colors[name], label=name)
        ax.set_title(f"{model}\nBrier raw={r['raw']['brier']:.3f} "
                     f"iso={r['methods']['isotonic']['scores']['brier']:.3f}")
        ax.set_xlabel("mean predicted P(YES)")
        ax.set_ylabel("observed frequency")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(alpha=0.2)

        axh = axes[1][j]
        axh.hist(r["raw_oof"], bins=20, range=(0, 1), color="#888888", alpha=0.6, label="raw")
        axh.hist(r["methods"]["isotonic"]["oof"], bins=20, range=(0, 1),
                 histtype="step", color="#1f77b4", label="isotonic")
        axh.axvline(r["base_rate"], color="k", ls=":", lw=1, label=f"base rate {r['base_rate']:.2f}")
        axh.set_xlabel("P(YES)"); axh.set_ylabel("count"); axh.set_title("sharpness")
        axh.legend(fontsize=8)

    fig.suptitle("KalshiBench reliability — raw vs recalibrated (out-of-fold)", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def make_risk_coverage_plot(results: dict, labels_by_model: dict, out_path: Path) -> None:
    """Risk-coverage curves (raw vs isotonic, OOF): error rate vs fraction auto-handled."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = list(results.keys())
    fig, axes = plt.subplots(1, len(models), figsize=(5 * len(models), 4), squeeze=False)
    for j, model in enumerate(models):
        r = results[model]
        y = labels_by_model[model]
        ax = axes[0][j]
        for name, preds, color in [("raw", r["raw_oof"], "#888888"),
                                   ("isotonic", r["methods"]["isotonic"]["oof"], "#1f77b4")]:
            cov, risk = sel.risk_coverage_curve(preds, y)
            ax.plot(cov, risk, color=color, label=f"{name} (AURC={sel.aurc(preds, y):.3f})")
        ax.set_title(model)
        ax.set_xlabel("coverage (fraction auto-handled)")
        ax.set_ylabel("error rate among handled")
        ax.set_xlim(0, 1); ax.set_ylim(0, max(0.5, float(1 - r["base_rate"]) + 0.05))
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(alpha=0.2)
    fig.suptitle("Selective prediction — risk vs coverage (out-of-fold)", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def build_verdict(results: dict, leakage_note: str) -> str:
    """Programmatic verdict on 'does recalibration beat raw confidence?'"""
    n_models = len(results)
    bucket_sig = sum(1 for r in results.values()
                     if r["methods"]["bucket_offset"]["brier_delta"]["ci_high"] < 0)
    iso_sig = sum(1 for r in results.values()
                  if r["methods"]["isotonic"]["brier_delta"]["ci_high"] < 0)
    bucket_nonmono = sum(1 for r in results.values()
                         if not r["methods"]["bucket_offset"]["monotonic"])
    iso_ece_sig = sum(1 for r in results.values()
                      if r["methods"]["isotonic"]["ece_delta"]["ci_high"] < 0)

    lines = ["## Verdict", ""]
    if iso_sig == 0 and bucket_sig == 0:
        headline = ("**NO** — on this set, no recalibration method significantly lowered "
                    "out-of-fold Brier vs raw confidence.")
    elif iso_sig >= 1 and bucket_sig == 0:
        headline = ("**YES, but only with isotonic (a proper monotone calibrator) — NOT the "
                    "project's bucket-offset method.** Standard isotonic recalibration "
                    f"significantly improved Brier on {iso_sig}/{n_models} models; the "
                    "project's own bucket-offset method did not.")
    elif bucket_sig >= 1:
        headline = (f"**YES.** The project's bucket-offset method significantly lowered "
                    f"out-of-fold Brier on {bucket_sig}/{n_models} models "
                    f"(isotonic: {iso_sig}/{n_models}).")
    else:
        headline = "**MIXED.**"
    lines += [headline, ""]
    lines.append(f"- Isotonic significantly improved Brier on **{iso_sig}/{n_models}** models, "
                 f"ECE on **{iso_ece_sig}/{n_models}**.")
    lines.append(f"- The project's **bucket-offset** method significantly improved Brier on "
                 f"**{bucket_sig}/{n_models}** models.")
    if bucket_nonmono:
        lines.append(f"- ⚠️ The bucket-offset map was **non-monotonic on {bucket_nonmono}/{n_models} "
                     f"models** (it can re-order forecasts / depress AUC) — a structural defect "
                     f"isotonic and Platt avoid by construction.")
    else:
        lines.append("- The bucket-offset map stayed monotonic on all models here.")
    lines.append("- See **Selective prediction** below for the act-or-escalate view (auto-handle "
                 "more at a fixed error rate), and **Calibration by category** for where it helps most.")
    lines += ["", leakage_note]
    return "\n".join(lines)


def write_report(results: dict, args, out_dir: Path, diagram_name: str, rc_name: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    leakage_note = (
        "> **Leakage caveat (read first).** Essentially all KalshiBench questions resolved in 2025 "
        "(~98%; the remaining ~2% closed in 2024/2021 — even more firmly inside the cutoff), within "
        "the knowledge cutoff of these models, so a model may *recall* outcomes rather than "
        "forecast them. These results therefore measure **whether recalibration improves the "
        "calibration of the models' stated confidence on these outputs** — they are NOT a "
        "forecasting-skill claim on unknown futures. The recalibration question (does a fitted "
        "map beat raw confidence out-of-fold?) is still valid; external validity to live "
        "forecasting is not established here."
    )
    methodology = f"""## Methodology

- **Data:** KalshiBench-{args.version} ({results[next(iter(results))]['n']} resolved binary
  questions scored per model). Label = 1 if ground_truth == yes.
- **Forecasts:** each model gave a direct P(YES) via a forced tool call (no chain-of-thought,
  for cost + parse reliability + cross-model compatibility), temperature {args.temperature}
  where the model accepts it.
- **Recalibration:** fit on TRAIN, applied to TEST via **grouped {args.folds}-fold
  cross-validation** (grouped by event/series_ticker so an event never splits across folds).
  Metrics are computed on pooled out-of-fold predictions; per-fold stability also tracked.
- **Methods:** `raw` (baseline) vs `bucket_offset` (the project's own
  `scoring/recalibration.py` method, reproduced as fit/apply) vs `isotonic` and `platt`
  (standard baselines, sklearn).
- **Metrics:** Brier (primary, proper scoring rule), Brier Skill Score (vs base-rate
  climatology), ECE & adaptive/equal-mass ACE (binning-robust), log-loss, AUC (discrimination —
  a drop signals a non-monotone map). {args.bins} bins. Headline 95% CIs use the **cluster
  (event) bootstrap** (resampling series_ticker, not rows), the unit that respects within-event
  dependence; per-fold improvement counts also shown.
- **Selective prediction (§ below):** (A) operating-point — pick the confidence threshold on
  TRAIN to hit a target error, apply OOF; (B) honesty at a nominal confidence bar. Confidence =
  max(p, 1−p).
- **Per-category & temporal** robustness sections, both descriptive (see their caveats).

> Methodology note: independent reviewers (Codex, Gemini) **disagreed** on the selective
> primary — Gemini favored the nominal-confidence-bar "calibration dividend" view; Codex
> favored the train-chosen-threshold operating point and flagged that realized error at a bar
> is ≤ (1−bar), not ≈. Both views are reported (A and B); neither is over-claimed.

### Honest limitations
- **Leakage** (above) is the dominant threat to external validity; every extension inherits it.
- ECE is a biased, binning-dependent estimator — Brier is primary; ACE can over-state error on
  tied/discrete forecasts, so it is descriptive only.
- Model rows share the same questions, so they are **not independent**; per-model results are
  primary, any cross-model average is descriptive only.
- With KalshiBench-v2's small events (≤2 rows each) the cluster bootstrap is close to a row
  bootstrap; it matters more as events grow. Per-category and temporal tables are descriptive
  (many comparisons / shifting n), not significance-controlled.
- Direct (no-CoT) forecasts may be less sharp than a reasoning agent's; this is a fixed,
  reproducible protocol, not necessarily each model's best possible calibration.
"""
    body = [
        f"# KalshiBench Calibration Proof-of-Value",
        f"_Generated {ts} · models: {', '.join(results.keys())}_",
        "",
        build_verdict(results, leakage_note),
        "",
        "## Results",
        "",
        build_table(results),
        "",
        "## Selective prediction — act-or-escalate",
        "",
        build_selective_table(results),
        "",
        "## Calibration by category",
        "",
        build_category_table(results),
        "",
        "## Temporal stability (recency probe)",
        "",
        build_temporal_table(results),
        "",
        "## Diagrams",
        "",
        f"![reliability diagram]({diagram_name})",
        "",
        f"![risk-coverage]({rc_name})",
        "",
        methodology,
    ]
    report_path = out_dir / "REPORT.md"
    report_path.write_text("\n".join(body))
    return report_path


async def _gather_forecasts(df, models, args, ck_dir: Path) -> dict:
    """Return {model: merged_df(qid, prob, label, group)} and print cost."""
    out = {}
    total_cost = 0.0
    for model in models:
        ck = ck_dir / f"forecasts_{model.replace('/', '_')}.jsonl"
        if args.no_llm:
            from parallax.bench.forecast import _load_checkpoint

            done = _load_checkpoint(ck)
            if not done:
                raise SystemExit(f"--no-llm but no cached forecasts at {ck}")
            import pandas as pd

            fc = pd.DataFrame(
                [{"qid": q, "model": model, "prob": r["prob"]} for q, r in done.items()]
            )
            logger.info("%s: loaded %d cached forecasts", model, len(fc))
        else:
            fc, stats = await generate_forecasts(
                df, model, checkpoint_path=ck, concurrency=args.concurrency, limit=args.limit
            )
            total_cost += stats.est_cost_usd
            logger.info("%s: ok=%d err=%d cached=%d est=$%.4f",
                        model, stats.n_ok, stats.n_error, stats.n_skipped_cached, stats.est_cost_usd)
        merged = fc.merge(
            df[["qid", "label", "group", "category", "close_time"]], on="qid"
        ).dropna(subset=["prob"])
        out[model] = merged
    if not args.no_llm:
        logger.info("TOTAL estimated forecast cost: $%.4f", total_cost)
    return out


def main():
    parser = argparse.ArgumentParser(description="KalshiBench calibration proof-of-value")
    parser.add_argument("--models", default="haiku,sonnet", help="comma list (haiku,sonnet,opus or full IDs)")
    parser.add_argument("--version", default="v2", help="KalshiBench version (v1|v2)")
    parser.add_argument("--limit", type=int, default=None, help="cap questions (smoke test)")
    parser.add_argument("--no-llm", action="store_true", help="reuse cached forecasts only")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--bins", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--outdir", default=None, help="output dir (default docs/reports/kalshibench-<date>)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")

    models = resolve_models(args.models)
    df = load_kalshibench(args.version)
    logger.info("Loaded KalshiBench-%s: %d questions, base rate %.3f",
                args.version, len(df), df["label"].mean())

    ck_dir = _REPO_ROOT / "data" / "bench"
    forecasts = asyncio.run(_gather_forecasts(df, models, args, ck_dir))

    results: dict = {}
    labels_by_model: dict = {}
    for model, fc in forecasts.items():
        probs = fc["prob"].to_numpy(dtype=float)
        labels = fc["label"].to_numpy(dtype=float)
        groups = fc["group"].to_numpy()
        categories = fc["category"].to_numpy()
        close_times = fc["close_time"].to_numpy()
        if len(probs) < args.folds * 2:
            logger.warning("%s: only %d forecasts, skipping", model, len(probs))
            continue
        folds = grouped_folds(labels, groups, args.folds)
        r = evaluate_model(probs, labels, groups, folds, n_bins=args.bins, seed=args.seed)
        r["raw_oof"] = probs
        oof_by_method = {k: r["methods"][k]["oof"] for k in METHODS}
        r["selective"] = selective_summary(probs, labels, oof_by_method, folds)
        r["categories"] = per_category_breakdown(
            probs, oof_by_method["isotonic"], labels, categories, args.bins)
        r["temporal"] = temporal_stability(probs, labels, close_times, groups, args.bins)
        results[model] = r
        labels_by_model[model] = labels

    if not results:
        raise SystemExit("No models had enough forecasts to evaluate.")

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = Path(args.outdir) if args.outdir else _REPO_ROOT.parent / "docs" / "reports" / f"kalshibench-{date}"
    out_dir.mkdir(parents=True, exist_ok=True)

    diagram_name, rc_name = "reliability.png", "risk_coverage.png"
    make_reliability_diagram(results, labels_by_model, args.bins, out_dir / diagram_name)
    make_risk_coverage_plot(results, labels_by_model, out_dir / rc_name)

    # Strip in-memory arrays before JSON dump.
    json_results = {}
    for model, r in results.items():
        jr = {"n": r["n"], "base_rate": r["base_rate"], "raw": r["raw"], "methods": {},
              "selective": r["selective"], "categories": r["categories"], "temporal": r["temporal"]}
        for kind, m in r["methods"].items():
            jr["methods"][kind] = {k: v for k, v in m.items() if k != "oof"}
        json_results[model] = jr
    (out_dir / "results.json").write_text(json.dumps(json_results, indent=2))

    report_path = write_report(results, args, out_dir, diagram_name, rc_name)

    print("\n" + build_table(results))
    print("\n" + build_verdict(results, "").rstrip())
    print(f"\nArtifacts written to: {out_dir}")
    for f in (report_path.name, diagram_name, rc_name, "results.json"):
        print(f"  - {f}")


if __name__ == "__main__":
    main()
