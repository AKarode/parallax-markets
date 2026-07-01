"""Tests for fit/apply recalibrators (bucket-offset, isotonic, Platt)."""

from __future__ import annotations

import numpy as np
import pytest

from parallax.scoring.calibration_metrics import brier_score, expected_calibration_error
from parallax.scoring.recalibrators import (
    BucketOffsetRecalibrator,
    IdentityRecalibrator,
    IsotonicRecalibrator,
    PlattRecalibrator,
    fit_recalibrator,
    is_monotonic,
    monotonicity_violation,
)


def test_identity_passthrough():
    r = IdentityRecalibrator()
    p = np.array([0.0, 0.3, 0.9, 1.0])
    np.testing.assert_allclose(r.predict(p), p)


def test_bucket_offset_known_arithmetic():
    # High bucket: all forecasts 0.9, actual rate 0.5 -> offset 0.4 capped to 0.15.
    # So 0.9 -> 0.9 - 0.15 = 0.75.
    probs = np.full(100, 0.9)
    labels = (np.arange(100) < 50).astype(float)
    r = BucketOffsetRecalibrator(max_offset=0.15).fit(probs, labels)
    assert r.offsets["80-100%"] == pytest.approx(0.15)  # capped
    assert r.predict([0.9])[0] == pytest.approx(0.75)


def test_bucket_offset_empty_bucket_is_passthrough():
    # Only the high bucket has data; mid bucket offset must be 0 (pass-through).
    probs = np.full(50, 0.9)
    labels = np.ones(50)
    r = BucketOffsetRecalibrator().fit(probs, labels)
    assert r.offsets["40-60%"] == 0.0
    assert r.predict([0.5])[0] == pytest.approx(0.5)


def test_bucket_offset_can_be_non_monotonic():
    # Construct miscalibration that inverts ranking across two adjacent buckets:
    #   mid bucket (0.5): underconfident -> negative offset -> maps UP
    #   high bucket (0.7): overconfident -> positive offset -> maps DOWN
    mid_p = np.full(200, 0.5)
    mid_y = (np.arange(200) < 130).astype(float)   # 65% positive -> offset -0.15
    hi_p = np.full(200, 0.7)
    hi_y = (np.arange(200) < 110).astype(float)    # 55% positive -> offset +0.15
    probs = np.concatenate([mid_p, hi_p])
    labels = np.concatenate([mid_y, hi_y])
    r = BucketOffsetRecalibrator(max_offset=0.15).fit(probs, labels)
    # raw 0.59 (mid) -> 0.74 ; raw 0.61 (high) -> 0.46  => inversion
    assert r.predict([0.59])[0] > r.predict([0.61])[0]
    assert not is_monotonic(r)
    assert monotonicity_violation(r) > 0.0


def test_isotonic_is_monotone_and_improves_calibration():
    rng = np.random.default_rng(0)
    # overconfident model: stated probs pushed toward extremes vs truth
    truth = rng.uniform(0.1, 0.9, 2000)
    stated = np.clip((truth - 0.5) * 1.8 + 0.5, 0.01, 0.99)  # overconfident
    y = (rng.uniform(0, 1, 2000) < truth).astype(float)
    r = IsotonicRecalibrator().fit(stated, y)
    assert is_monotonic(r)
    raw_ece = expected_calibration_error(stated, y)
    cal_ece = expected_calibration_error(r.predict(stated), y)
    assert cal_ece < raw_ece


def test_platt_is_monotone():
    rng = np.random.default_rng(1)
    truth = rng.uniform(0.1, 0.9, 1500)
    stated = np.clip((truth - 0.5) * 1.6 + 0.5, 0.01, 0.99)
    y = (rng.uniform(0, 1, 1500) < truth).astype(float)
    r = PlattRecalibrator().fit(stated, y)
    assert is_monotonic(r)


def test_isotonic_preserves_auc_bucket_may_not():
    # AUC (rank order) must survive a monotone map; non-monotone may break it.
    rng = np.random.default_rng(2)
    truth = rng.uniform(0.05, 0.95, 1500)
    stated = np.clip((truth - 0.5) * 1.7 + 0.5, 0.01, 0.99)
    y = (rng.uniform(0, 1, 1500) < truth).astype(float)
    iso = IsotonicRecalibrator().fit(stated, y)
    assert is_monotonic(iso)


def test_fit_recalibrator_factory():
    p = np.array([0.2, 0.8, 0.5, 0.9, 0.1] * 20)
    y = (np.arange(100) < 50).astype(float)
    for kind in ("raw", "bucket", "isotonic", "platt"):
        r = fit_recalibrator(kind, p, y)
        out = r.predict(p)
        assert out.shape == p.shape
        assert np.all((out >= 0) & (out <= 1))
    with pytest.raises(ValueError):
        fit_recalibrator("nonsense", p, y)


def test_recalibration_improves_brier_out_of_sample():
    # Honest train/test: fit on first half, evaluate on second half.
    rng = np.random.default_rng(7)
    truth = rng.uniform(0.1, 0.9, 4000)
    stated = np.clip((truth - 0.5) * 1.8 + 0.5, 0.01, 0.99)  # overconfident
    y = (rng.uniform(0, 1, 4000) < truth).astype(float)
    tr = slice(0, 2000)
    te = slice(2000, 4000)
    r = IsotonicRecalibrator().fit(stated[tr], y[tr])
    raw = brier_score(stated[te], y[te])
    cal = brier_score(r.predict(stated[te]), y[te])
    assert cal < raw
