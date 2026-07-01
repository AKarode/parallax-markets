"""Pure-array calibration metrics: Brier, log-loss, ECE, reliability curve.

The existing ``scoring/calibration.py`` computes bucketed curves *from DuckDB
tables* (the live signal ledger). This module adds the standard probabilistic-
forecast scoring metrics the project was missing -- Brier score, log-loss,
Expected/Maximum Calibration Error, the reliability curve, and the Murphy
(reliability/resolution/uncertainty) decomposition -- operating on plain arrays.

Keeping them DB-free means they can score *any* ``(probability, outcome)`` set
-- including the KalshiBench benchmark -- without the live trading database, and
keeps them trivially unit-testable against known-answer inputs.

All functions take ``probs`` in [0, 1] and binary ``labels`` in {0, 1}.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Clip for log-loss so a confident-wrong forecast does not yield infinite loss.
LOG_LOSS_EPS = 1e-15


def _validate(probs, labels) -> tuple[np.ndarray, np.ndarray]:
    """Coerce to float arrays and validate shape / range / binary labels."""
    p = np.asarray(probs, dtype=float)
    y = np.asarray(labels, dtype=float)
    if p.shape != y.shape:
        raise ValueError(f"probs/labels shape mismatch: {p.shape} vs {y.shape}")
    if p.ndim != 1:
        raise ValueError(f"expected 1-D arrays, got ndim={p.ndim}")
    if p.size == 0:
        raise ValueError("empty input")
    if np.any(~np.isfinite(p)) or np.any((p < 0.0) | (p > 1.0)):
        raise ValueError("probs must be finite and within [0, 1]")
    uniq = np.unique(y)
    if not np.all(np.isin(uniq, (0.0, 1.0))):
        raise ValueError(f"labels must be binary 0/1, saw {uniq.tolist()}")
    return p, y


def brier_score(probs, labels) -> float:
    """Mean squared error of probabilistic forecasts. Lower is better, range [0, 1]."""
    p, y = _validate(probs, labels)
    return float(np.mean((p - y) ** 2))


def log_loss(probs, labels, eps: float = LOG_LOSS_EPS) -> float:
    """Binary cross-entropy (natural log). Lower is better. Clipped at ``eps``."""
    p, y = _validate(probs, labels)
    p = np.clip(p, eps, 1.0 - eps)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def accuracy(probs, labels, threshold: float = 0.5) -> float:
    """Fraction correct when thresholding the probability (default 0.5)."""
    p, y = _validate(probs, labels)
    return float(np.mean((p >= threshold).astype(float) == y))


def base_rate(labels) -> float:
    """Observed positive rate -- the no-skill 'always predict the base rate' anchor."""
    y = np.asarray(labels, dtype=float)
    return float(np.mean(y))


@dataclass(frozen=True)
class ReliabilityBin:
    """One bin of a reliability curve. ``mean_pred``/``frac_pos`` are NaN if empty."""

    lo: float
    hi: float
    count: int
    mean_pred: float
    frac_pos: float


def reliability_curve(probs, labels, n_bins: int = 10) -> list[ReliabilityBin]:
    """Bin forecasts into ``n_bins`` equal-width bins over [0, 1].

    Returns one ``ReliabilityBin`` per bin (including empty ones, so the curve
    has a stable shape). The last bin is closed on the right so p == 1.0 lands
    in it rather than overflowing.
    """
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")
    p, y = _validate(probs, labels)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # Bin via floor(p * n_bins) with a tiny epsilon so exact round deciles
    # (0.3/0.6/0.7, whose linspace edges carry float dust) land in the correct
    # [lo, hi) bin instead of one bin low; p==1.0 clips into the last bin.
    idx = np.clip(np.floor(p * n_bins + 1e-9).astype(int), 0, n_bins - 1)
    out: list[ReliabilityBin] = []
    for b in range(n_bins):
        mask = idx == b
        count = int(mask.sum())
        if count:
            out.append(
                ReliabilityBin(
                    lo=float(edges[b]),
                    hi=float(edges[b + 1]),
                    count=count,
                    mean_pred=float(p[mask].mean()),
                    frac_pos=float(y[mask].mean()),
                )
            )
        else:
            out.append(
                ReliabilityBin(float(edges[b]), float(edges[b + 1]), 0, float("nan"), float("nan"))
            )
    return out


def expected_calibration_error(probs, labels, n_bins: int = 10) -> float:
    """ECE: sample-weighted mean gap between confidence and accuracy per bin.

    Lower is better. Note ECE is a *biased*, binning-dependent estimator -- it
    generally shrinks as ``n_bins`` drops and is noisy in sparse bins. Always
    pair it with Brier (a proper scoring rule) and report ``n``.
    """
    p, y = _validate(probs, labels)
    bins = reliability_curve(p, y, n_bins)
    n = p.size
    return float(
        sum((b.count / n) * abs(b.mean_pred - b.frac_pos) for b in bins if b.count)
    )


def maximum_calibration_error(probs, labels, n_bins: int = 10) -> float:
    """MCE: worst-case bin calibration gap. Lower is better."""
    p, y = _validate(probs, labels)
    bins = reliability_curve(p, y, n_bins)
    gaps = [abs(b.mean_pred - b.frac_pos) for b in bins if b.count]
    return float(max(gaps)) if gaps else 0.0


def adaptive_calibration_error(probs, labels, n_bins: int = 10) -> float:
    """Adaptive ECE using equal-MASS bins (each bin has ~equal sample count).

    Standard equal-width ECE is biased by where bin boundaries fall and is noisy
    in sparse bins. Equal-mass bins put the same number of samples in every bin,
    which removes the empty-bin/sparse-bin artifact. Lower is better.

    Caveat: this is the standard equal-mass definition and does NOT merge tied
    forecast values -- a block of identical probabilities can be split across
    bins, which can *overstate* miscalibration on heavily discretized forecasts
    (the typical LLM regime). Prefer Brier for decisions; treat ACE as one of
    several descriptive calibration views, not a sole criterion.
    """
    p, y = _validate(probs, labels)
    n = p.size
    n_bins = max(1, min(n_bins, n))
    order = np.argsort(p, kind="mergesort")
    p_sorted, y_sorted = p[order], y[order]
    # Split sorted indices into n_bins near-equal contiguous chunks.
    chunks = np.array_split(np.arange(n), n_bins)
    ece = 0.0
    for chunk in chunks:
        if chunk.size == 0:
            continue
        conf = p_sorted[chunk].mean()
        acc = y_sorted[chunk].mean()
        ece += (chunk.size / n) * abs(conf - acc)
    return float(ece)


def auc_roc(probs, labels) -> float:
    """Area under the ROC curve via the Mann-Whitney U statistic (rank-based).

    Pure-numpy, handles ties with average ranks. Measures *discrimination* (rank
    ordering), which is invariant to any monotone recalibration -- so a drop in
    AUC after recalibration is direct evidence the map is NON-monotone (it
    reordered forecasts), the disqualifying failure mode for bucket-offset.
    Returns NaN if labels are single-class (AUC undefined).
    """
    p, y = _validate(probs, labels)
    n_pos = float(y.sum())
    n_neg = float(y.size - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    # Average ranks (1-based) to handle ties correctly.
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(p.size, dtype=float)
    sorted_p = p[order]
    i = 0
    while i < p.size:
        j = i
        while j + 1 < p.size and sorted_p[j + 1] == sorted_p[i]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-based average rank for the tie group
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1
    sum_ranks_pos = ranks[y == 1].sum()
    auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)


def brier_decomposition(probs, labels, n_bins: int = 10) -> dict[str, float]:
    """Murphy decomposition of the (binned) Brier score.

    BS_binned = reliability - resolution + uncertainty, using each bin's mean
    forecast as its representative. ``reliability`` (lower better) measures
    miscalibration; ``resolution`` (higher better) measures discrimination;
    ``uncertainty`` is the irreducible base-rate variance. ``brier_via_decomp``
    is the binned reconstruction and will differ slightly from the raw Brier
    because of within-bin forecast spread.
    """
    p, y = _validate(probs, labels)
    n = p.size
    o_bar = float(y.mean())
    uncertainty = o_bar * (1.0 - o_bar)
    bins = reliability_curve(p, y, n_bins)
    reliability = sum((b.count / n) * (b.mean_pred - b.frac_pos) ** 2 for b in bins if b.count)
    resolution = sum((b.count / n) * (b.frac_pos - o_bar) ** 2 for b in bins if b.count)
    return {
        "reliability": float(reliability),
        "resolution": float(resolution),
        "uncertainty": float(uncertainty),
        "brier_via_decomp": float(reliability - resolution + uncertainty),
    }


def bootstrap_metric_diff(
    probs_baseline,
    probs_candidate,
    labels,
    metric_fn,
    n_boot: int = 2000,
    seed: int = 0,
) -> dict[str, float]:
    """Paired bootstrap CI for ``metric(candidate) - metric(baseline)``.

    Resamples sample indices with replacement (paired: the same indices apply to
    both forecast sets and the labels), recomputing the metric difference each
    draw. For Brier/ECE (lower=better) a NEGATIVE diff means the candidate is
    better; ``p_improve`` is the fraction of resamples where it improved.

    Returns: ``diff`` (point estimate), ``ci_low``/``ci_high`` (95% percentile),
    ``p_improve``.
    """
    pb, y = _validate(probs_baseline, labels)
    pc, _ = _validate(probs_candidate, labels)
    n = y.size
    rng = np.random.default_rng(seed)
    point = metric_fn(pc, y) - metric_fn(pb, y)
    diffs = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        diffs[i] = metric_fn(pc[idx], y[idx]) - metric_fn(pb[idx], y[idx])
    # Drop non-finite diffs (e.g. a metric like AUC returns NaN on a single-class
    # resample) so the CI and p_improve are computed over valid replicates only.
    finite = diffs[np.isfinite(diffs)]
    if finite.size == 0:
        return {"diff": float(point), "ci_low": float("nan"),
                "ci_high": float("nan"), "p_improve": float("nan")}
    lo, hi = np.percentile(finite, [2.5, 97.5])
    return {
        "diff": float(point),
        "ci_low": float(lo),
        "ci_high": float(hi),
        "p_improve": float(np.mean(finite < 0.0)),
    }


def brier_skill_score(probs, labels, ref_prob: float | None = None) -> float:
    """Brier Skill Score vs a climatology baseline. >0 beats baseline, lower bound -inf.

    BSS = 1 - Brier(forecast) / Brier(climatology). Climatology is a constant
    forecast equal to ``ref_prob`` (default: the base rate of ``labels``, computed
    on the same slice -- the standard no-skill anchor). Returns NaN if the
    baseline Brier is 0 (single-class slice).
    """
    p, y = _validate(probs, labels)
    ref = float(y.mean()) if ref_prob is None else float(ref_prob)
    brier_ref = float(np.mean((ref - y) ** 2))
    if brier_ref == 0.0:
        return float("nan")
    return float(1.0 - brier_score(p, y) / brier_ref)


def bootstrap_metric_diff_grouped(
    probs_baseline,
    probs_candidate,
    labels,
    groups,
    metric_fn,
    n_boot: int = 2000,
    seed: int = 0,
) -> dict[str, float]:
    """Cluster bootstrap of ``metric(candidate) - metric(baseline)``, resampling GROUPS.

    Like :func:`bootstrap_metric_diff` but resamples whole event clusters
    (``groups``, e.g. series_ticker) with replacement rather than individual rows
    -- the correct unit when rows within a group are dependent (avoids the
    anti-conservative CI of row resampling). The same resampled cluster set is
    used for both forecast sets (paired). With mostly tiny (1-2 row) groups this
    is close to the row bootstrap; it matters more as group sizes grow.
    """
    pb, y = _validate(probs_baseline, labels)
    pc, _ = _validate(probs_candidate, labels)
    g = np.asarray(groups)
    if g.shape[0] != y.shape[0]:
        raise ValueError("groups length must match labels")
    uniq = np.unique(g)
    # Precompute row indices per group.
    idx_by_group = {gv: np.where(g == gv)[0] for gv in uniq}
    rng = np.random.default_rng(seed)
    point = metric_fn(pc, y) - metric_fn(pb, y)
    diffs = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        chosen = rng.integers(0, uniq.size, uniq.size)
        idx = np.concatenate([idx_by_group[uniq[c]] for c in chosen])
        try:
            diffs[i] = metric_fn(pc[idx], y[idx]) - metric_fn(pb[idx], y[idx])
        except Exception:
            diffs[i] = np.nan
    finite = diffs[np.isfinite(diffs)]
    if finite.size == 0:
        return {"diff": float(point), "ci_low": float("nan"),
                "ci_high": float("nan"), "p_improve": float("nan")}
    lo, hi = np.percentile(finite, [2.5, 97.5])
    return {"diff": float(point), "ci_low": float(lo), "ci_high": float(hi),
            "p_improve": float(np.mean(finite < 0.0))}


def score_all(probs, labels, n_bins: int = 10) -> dict[str, float]:
    """Convenience bundle of the headline metrics for one forecast set."""
    p, y = _validate(probs, labels)
    return {
        "n": int(p.size),
        "brier": brier_score(p, y),
        "ece": expected_calibration_error(p, y, n_bins),
        "ace": adaptive_calibration_error(p, y, n_bins),
        "mce": maximum_calibration_error(p, y, n_bins),
        "log_loss": log_loss(p, y),
        "auc": auc_roc(p, y),
        "bss": brier_skill_score(p, y),
        "accuracy": accuracy(p, y),
        "base_rate": base_rate(y),
    }
