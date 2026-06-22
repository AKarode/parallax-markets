"""Selective prediction ("act-or-escalate") metrics for binary forecasts.

Answers the half of the calibration proof-of-value question that pure Brier/ECE
don't: *if you only act when confident and escalate the rest, does recalibration
let you auto-handle MORE questions at a fixed error rate?*

Two views, both on held-out (out-of-fold) predictions:

- **Stated-confidence honesty** (``selective_at_confidence``): at a nominal bar c
  (e.g. 0.90), auto-handle questions with confidence >= c and report coverage +
  REALIZED error. A *calibrated* model's realized error is <= (1-c) (not exactly
  1-c: it is ``E[min(p,1-p) | max(p,1-p)>=c]``); an *overconfident* raw model's
  realized error EXCEEDS (1-c). The honesty gap = realized - (1-c).
- **Target-error operating point** (``operating_threshold`` + ``apply_threshold``):
  the rigorous "auto-handle more at a fixed error rate" answer -- pick the
  confidence threshold on a TRAIN slice to hit a target error, apply it to a
  disjoint TEST slice, and read off coverage + realized error there (non-optimistic).
- **Ranking** (``risk_coverage_curve`` / ``aurc`` / ``coverage_at_error``):
  sort by confidence and sweep coverage; area under the risk-coverage curve.
  Note: ``coverage_at_error`` on the SAME set it is read from is optimistic
  (oracle threshold) -- use the train/test ``operating_threshold`` path for headlines.

Confidence for a binary forecast p is ``max(p, 1-p)`` and the predicted class is
``1[p >= 0.5]``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from parallax.scoring.calibration_metrics import _validate


def confidence(probs) -> np.ndarray:
    """Distance-from-half confidence of a binary forecast: max(p, 1-p) in [0.5, 1]."""
    p = np.asarray(probs, dtype=float)
    return np.maximum(p, 1.0 - p)


def _errors(probs: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """0/1 misclassification at the 0.5 threshold (ties p==0.5 -> predict 1)."""
    pred = (probs >= 0.5).astype(float)
    return (pred != labels).astype(float)


@dataclass(frozen=True)
class SelectivePoint:
    confidence_level: float
    coverage: float        # fraction auto-handled (confidence >= level)
    realized_error: float  # error rate among auto-handled (NaN if none)
    n_covered: int
    promised_error: float  # 1 - confidence_level, the calibrated target


def selective_at_confidence(probs, labels, level: float) -> SelectivePoint:
    """Operational act-or-escalate at a fixed stated-confidence bar ``level``.

    Auto-handle items with confidence >= level; report coverage and the realized
    error among them. For a calibrated model realized_error ~ 1-level.
    """
    p, y = _validate(probs, labels)
    conf = confidence(p)
    mask = conf >= level
    n_cov = int(mask.sum())
    if n_cov == 0:
        realized = float("nan")
    else:
        realized = float(_errors(p[mask], y[mask]).mean())
    return SelectivePoint(
        confidence_level=float(level),
        coverage=float(n_cov / p.size),
        realized_error=realized,
        n_covered=n_cov,
        promised_error=float(1.0 - level),
    )


def risk_coverage_curve(probs, labels):
    """Risk (error rate) vs coverage, sweeping from most- to least-confident.

    Returns ``(coverage, risk)`` arrays of length n: at each prefix of the
    confidence-sorted items, coverage = k/n and risk = error rate over the top-k.
    Ties in confidence are broken by sort order (deterministic, stable).
    """
    p, y = _validate(probs, labels)
    errs = _errors(p, y)
    order = np.argsort(-confidence(p), kind="mergesort")  # most confident first
    cum_err = np.cumsum(errs[order])
    k = np.arange(1, p.size + 1)
    coverage = k / p.size
    risk = cum_err / k
    return coverage, risk


def aurc(probs, labels) -> float:
    """Area under the risk-coverage curve (trapezoidal). Lower is better.

    Undefined (NaN) for a single forecast -- one coverage point has no area, and
    np.trapz would collapse it to a misleading 0.0 regardless of correctness.
    """
    coverage, risk = risk_coverage_curve(probs, labels)
    if coverage.size < 2:
        return float("nan")
    return float(np.trapz(risk, coverage))


def operating_threshold(probs, labels, target_error: float) -> float:
    """Min confidence to accept so train error stays <= target, maximizing coverage.

    Returns a confidence threshold in [0.5, 1] to be applied to a *disjoint* test
    set (accept items with confidence >= threshold). Returns ``inf`` if no
    accept-set achieves the target (accept nothing). This is the honest "fit the
    operating point on train, evaluate on test" path that avoids the optimism of
    choosing the threshold on the evaluation set itself.

    Tie-safe: the threshold is evaluated against the *actual* accepted set
    (``confidence >= v``) at each distinct confidence level, NOT a sorted prefix.
    A prefix-index cutoff would silently admit the rest of a tied-confidence block
    when consumed via ``>=`` (the common case for discretized LLM probabilities),
    blowing past the target.
    """
    p, y = _validate(probs, labels)
    conf = confidence(p)
    errs = _errors(p, y)
    # Ascending distinct confidence levels: lower v == larger accepted set. Take
    # the lowest v (max coverage) whose accepted-set error meets the target.
    for v in np.unique(conf):
        if errs[conf >= v].mean() <= target_error + 1e-12:
            return float(v)
    return float("inf")


def apply_threshold(probs, labels, threshold: float) -> dict:
    """Accept items with confidence >= threshold; report coverage + realized error."""
    p, y = _validate(probs, labels)
    mask = confidence(p) >= threshold
    n_cov = int(mask.sum())
    realized = float(_errors(p[mask], y[mask]).mean()) if n_cov else float("nan")
    return {"coverage": float(n_cov / p.size), "realized_error": realized, "n_covered": n_cov}


def coverage_at_error(probs, labels, target_error: float) -> dict:
    """Largest coverage whose top-confidence prefix keeps error <= target_error.

    Returns ``{coverage, realized_error, n}``. If even the single most-confident
    item is wrong (and target < its error), coverage is 0.
    """
    p, y = _validate(probs, labels)
    coverage, risk = risk_coverage_curve(p, y)
    ok = np.where(risk <= target_error + 1e-12)[0]
    if ok.size == 0:
        return {"coverage": 0.0, "realized_error": 0.0, "n": 0}
    k = int(ok.max()) + 1  # largest prefix index satisfying the bound
    return {"coverage": float(k / p.size), "realized_error": float(risk[k - 1]), "n": k}
