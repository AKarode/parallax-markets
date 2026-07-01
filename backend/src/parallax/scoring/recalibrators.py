"""Fit/apply recalibration maps for honest train->test evaluation.

The live ``scoring/recalibration.py`` recalibrates a *single* probability against
calibration stats read live from DuckDB. That in-place design can't answer the
proof-of-value question ("does recalibration beat raw confidence on held-out
data?") because it has no train/test separation -- recalibrating on the same
data you fit on trivially wins.

This module factors the same idea into fit/apply objects so a map learned on a
TRAIN slice can be applied to a disjoint TEST slice:

- ``BucketOffsetRecalibrator`` -- the project's own method, reusing the exact
  bucket boundaries and capped-offset formula from ``recalibration.py``.
- ``IsotonicRecalibrator`` -- standard monotone calibration (sklearn).
- ``PlattRecalibrator`` -- logistic (sigmoid) calibration in logit space.

Each exposes ``.name`` and ``.predict(probs) -> np.ndarray``. ``is_monotonic``
flags the bucket method's disqualifying failure mode (rank inversion), which a
proper calibrator cannot have.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Reuse the EXACT bucket scheme + classifier from the live recalibrator so this
# benchmark scores the project's real method, not a lookalike.
from parallax.scoring.recalibration import _BUCKET_RANGES, _bucket_for_prob


class Recalibrator:
    """Base interface: a fitted map from raw probability -> calibrated probability."""

    name: str = "base"

    def predict(self, probs) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class IdentityRecalibrator(Recalibrator):
    """The raw forecast, unchanged -- the baseline every method must beat."""

    name: str = "raw"

    def predict(self, probs) -> np.ndarray:
        return np.clip(np.asarray(probs, dtype=float), 0.0, 1.0)


class BucketOffsetRecalibrator(Recalibrator):
    """Parallax's own bucket-offset method, in fit/apply form.

    Fit: for each of the 5 buckets (0-20 .. 80-100%) compute
    ``offset = mean(raw_prob) - mean(outcome)`` on the TRAIN slice, capped to
    +/- ``max_offset``. Apply: ``calibrated = raw - offset[bucket]``, clamped to
    [0, 1]. This is exactly the arithmetic in ``recalibration.recalibrate_probability``.

    Buckets with no training samples get a zero offset (pass-through), matching
    the live code's "no data for this bucket -> return raw" behavior.
    """

    name = "bucket_offset"

    def __init__(self, max_offset: float = 0.15):
        self.max_offset = max_offset
        self.offsets: dict[str, float] = {}

    def fit(self, probs, labels) -> "BucketOffsetRecalibrator":
        p = np.asarray(probs, dtype=float)
        y = np.asarray(labels, dtype=float)
        self.offsets = {}
        for lo, hi, label in _BUCKET_RANGES:
            mask = (p >= lo) & (p < hi)
            if not mask.any():
                self.offsets[label] = 0.0
                continue
            # round(...,3) mirrors the live calibration_curve SQL so the fitted
            # offsets are bit-identical to recalibrate_probability's.
            avg_predicted = round(float(p[mask].mean()), 3)
            actual_rate = round(float(y[mask].mean()), 3)
            offset = avg_predicted - actual_rate  # positive => model overestimates
            offset = max(-self.max_offset, min(self.max_offset, offset))
            self.offsets[label] = offset
        return self

    def predict(self, probs) -> np.ndarray:
        p = np.asarray(probs, dtype=float)
        out = np.empty_like(p)
        for i, prob in enumerate(p):
            bucket = _bucket_for_prob(float(prob))
            offset = self.offsets.get(bucket, 0.0)
            out[i] = min(1.0, max(0.0, float(prob) - offset))
        return out


class IsotonicRecalibrator(Recalibrator):
    """Isotonic regression: the standard *monotone* nonparametric calibrator.

    Monotone by construction, so it can never reorder forecasts (AUC-preserving).
    Clips out-of-range inputs to the trained support.
    """

    name = "isotonic"

    def __init__(self):
        self._model = None

    def fit(self, probs, labels) -> "IsotonicRecalibrator":
        from sklearn.isotonic import IsotonicRegression

        p = np.asarray(probs, dtype=float)
        y = np.asarray(labels, dtype=float)
        self._model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self._model.fit(p, y)
        return self

    def predict(self, probs) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("IsotonicRecalibrator.predict called before fit")
        p = np.asarray(probs, dtype=float)
        return np.clip(self._model.predict(p), 0.0, 1.0)


class PlattRecalibrator(Recalibrator):
    """Platt scaling: logistic regression of outcome on the forecast's logit.

    Fits ``P_cal = sigmoid(a * logit(p) + b)``. Monotone for a >= 0 (the usual
    case). A 2-parameter parametric calibrator -- robust when data is scarce, but
    can't fix non-sigmoidal miscalibration the way isotonic can.
    """

    name = "platt"

    def __init__(self, eps: float = 1e-6):
        self.eps = eps
        self._model = None

    def _logit(self, p: np.ndarray) -> np.ndarray:
        p = np.clip(p, self.eps, 1.0 - self.eps)
        return np.log(p / (1.0 - p))

    def fit(self, probs, labels) -> "PlattRecalibrator":
        from sklearn.linear_model import LogisticRegression

        p = np.asarray(probs, dtype=float)
        y = np.asarray(labels, dtype=float)
        x = self._logit(p).reshape(-1, 1)
        self._model = LogisticRegression(C=1e6, solver="lbfgs")
        self._model.fit(x, y)
        return self

    def predict(self, probs) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("PlattRecalibrator.predict called before fit")
        p = np.asarray(probs, dtype=float)
        x = self._logit(p).reshape(-1, 1)
        return np.clip(self._model.predict_proba(x)[:, 1], 0.0, 1.0)


def fit_recalibrator(kind: str, probs, labels, **kwargs) -> Recalibrator:
    """Factory: fit a recalibrator of ``kind`` on (probs, labels)."""
    kind = kind.lower()
    if kind in ("raw", "identity"):
        return IdentityRecalibrator()
    if kind in ("bucket", "bucket_offset"):
        return BucketOffsetRecalibrator(**kwargs).fit(probs, labels)
    if kind == "isotonic":
        return IsotonicRecalibrator().fit(probs, labels)
    if kind == "platt":
        return PlattRecalibrator(**kwargs).fit(probs, labels)
    raise ValueError(f"unknown recalibrator kind: {kind!r}")


def is_monotonic(recal: Recalibrator, n_grid: int = 1001, tol: float = 1e-9) -> bool:
    """True if the fitted map is non-decreasing across [0, 1].

    A non-monotone map reorders forecasts (a higher raw prob can map below a
    lower one) -- the disqualifying failure mode for the bucket-offset method
    that a reviewer flagged. Isotonic/Platt are monotone by construction.
    """
    grid = np.linspace(0.0, 1.0, n_grid)
    mapped = recal.predict(grid)
    return bool(np.all(np.diff(mapped) >= -tol))


def monotonicity_violation(recal: Recalibrator, n_grid: int = 1001) -> float:
    """Largest backwards step in the fitted map (0.0 == perfectly monotone)."""
    grid = np.linspace(0.0, 1.0, n_grid)
    mapped = recal.predict(grid)
    drops = -np.diff(mapped)
    return float(max(0.0, drops.max())) if drops.size else 0.0
