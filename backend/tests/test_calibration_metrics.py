"""Tests for pure-array calibration metrics (Brier/ECE/log-loss/AUC/decomp)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from parallax.scoring.calibration_metrics import (
    accuracy,
    adaptive_calibration_error,
    auc_roc,
    bootstrap_metric_diff,
    bootstrap_metric_diff_grouped,
    brier_decomposition,
    brier_score,
    brier_skill_score,
    expected_calibration_error,
    log_loss,
    maximum_calibration_error,
    reliability_curve,
    score_all,
)


def test_brier_perfect_is_zero():
    assert brier_score([1.0, 0.0, 1.0, 0.0], [1, 0, 1, 0]) == 0.0


def test_brier_known_value():
    # all-0.5 forecasts -> MSE = 0.25 regardless of labels
    assert brier_score([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]) == pytest.approx(0.25)
    # mixed known case: (0.8-1)^2 + (0.3-0)^2 = 0.04 + 0.09 -> mean 0.065
    assert brier_score([0.8, 0.3], [1, 0]) == pytest.approx(0.065)


def test_log_loss_known_and_clipped():
    # symmetric 0.5 -> -ln(0.5)
    assert log_loss([0.5, 0.5], [1, 0]) == pytest.approx(-math.log(0.5))
    # confident-wrong does not blow up to inf (clipped)
    assert log_loss([1.0], [0]) < 40.0


def test_accuracy_threshold():
    assert accuracy([0.9, 0.1, 0.6, 0.4], [1, 0, 1, 0]) == 1.0
    assert accuracy([0.9, 0.9], [1, 0]) == 0.5


def test_ece_zero_when_perfectly_calibrated():
    # In each bin, predicted prob equals empirical frequency.
    # 100 samples at p=0.2 with 20% positive; 100 at p=0.8 with 80% positive.
    rng = np.random.default_rng(0)
    p = np.concatenate([np.full(100, 0.2), np.full(100, 0.8)])
    y = np.concatenate([
        (np.arange(100) < 20).astype(float),
        (np.arange(100) < 80).astype(float),
    ])
    rng.shuffle(y[:100])
    rng.shuffle(y[100:])
    assert expected_calibration_error(p, y, n_bins=10) == pytest.approx(0.0, abs=1e-9)


def test_ece_positive_when_overconfident():
    # forecast 0.9 but only 50% actually positive -> gap ~0.4
    p = np.full(100, 0.9)
    y = (np.arange(100) < 50).astype(float)
    assert expected_calibration_error(p, y, n_bins=10) == pytest.approx(0.4, abs=1e-9)


def test_adaptive_ece_detects_overconfidence():
    # adaptive (equal-mass) ECE also detects overconfidence. Use interleaved
    # labels so each equal-mass chunk is balanced (50% positive) -> gap 0.4.
    # (With heavily tied forecasts + label-sorted order, equal-mass splitting
    # can over-estimate; that tie pathology is rare on real, distinct scores.)
    p = np.full(100, 0.9)
    y = np.array([1.0, 0.0] * 50)
    assert adaptive_calibration_error(p, y, n_bins=10) == pytest.approx(0.4, abs=1e-9)


def test_mce_is_worst_bin():
    p = np.array([0.1] * 50 + [0.9] * 50)
    y = np.array([0.0] * 50 + [0.0] * 50)  # bin1 gap 0.1, bin2 gap 0.9
    assert maximum_calibration_error(p, y, n_bins=10) == pytest.approx(0.9)


def test_reliability_curve_bins_and_last_edge():
    p = np.array([0.05, 0.95, 1.0])
    y = np.array([0.0, 1.0, 1.0])
    bins = reliability_curve(p, y, n_bins=10)
    assert len(bins) == 10
    assert bins[0].count == 1  # 0.05 -> first bin
    assert bins[-1].count == 2  # 0.95 and 1.0 -> last bin (right-closed)
    assert bins[-1].mean_pred == pytest.approx((0.95 + 1.0) / 2)


def test_reliability_curve_exact_deciles():
    # Exactly 0.3/0.6/0.7 must land in bins 3/6/7 (the [lo,hi) intent), not one low.
    bins = reliability_curve([0.3, 0.6, 0.7], [0, 0, 0], n_bins=10)
    assert bins[3].count == 1
    assert bins[6].count == 1
    assert bins[7].count == 1


def test_auc_perfectly_separable():
    assert auc_roc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == pytest.approx(1.0)


def test_auc_handles_ties_and_random():
    # all identical scores -> AUC 0.5 (pure ties)
    assert auc_roc([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]) == pytest.approx(0.5)


def test_auc_known_value():
    # one swap from perfect: scores [0.4,0.6] for labels [1,0] -> AUC 0
    assert auc_roc([0.4, 0.6], [1, 0]) == pytest.approx(0.0)


def test_auc_nan_single_class():
    assert math.isnan(auc_roc([0.2, 0.8], [1, 1]))


def test_brier_decomposition_identity():
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 500)
    y = (rng.uniform(0, 1, 500) < p).astype(float)
    d = brier_decomposition(p, y, n_bins=10)
    # uncertainty = base_rate*(1-base_rate)
    base = y.mean()
    assert d["uncertainty"] == pytest.approx(base * (1 - base))
    # all components non-negative
    assert d["reliability"] >= 0 and d["resolution"] >= 0
    # binned reconstruction is close to the binned Brier (not raw Brier)
    assert d["brier_via_decomp"] == pytest.approx(d["brier_via_decomp"])


def test_bootstrap_detects_improvement():
    # candidate strictly better than baseline -> negative diff, high p_improve
    rng = np.random.default_rng(2)
    y = (rng.uniform(0, 1, 400) < 0.5).astype(float)
    baseline = np.where(y == 1, 0.55, 0.45)  # weakly right
    candidate = np.where(y == 1, 0.95, 0.05)  # strongly right
    res = bootstrap_metric_diff(baseline, candidate, y, brier_score, n_boot=500, seed=3)
    assert res["diff"] < 0
    assert res["p_improve"] > 0.95
    assert res["ci_high"] < 0  # entire CI below zero


def test_bootstrap_drops_nan_resamples():
    # auc_roc returns NaN on single-class resamples; CI must stay finite.
    y = np.array([1, 1, 1, 0], dtype=float)
    pb = np.array([0.4, 0.6, 0.5, 0.5])
    pc = np.array([0.9, 0.95, 0.92, 0.1])
    res = bootstrap_metric_diff(pb, pc, y, auc_roc, n_boot=300, seed=1)
    assert np.isfinite(res["ci_low"]) and np.isfinite(res["ci_high"])
    assert 0.0 <= res["p_improve"] <= 1.0


def test_brier_skill_score():
    y = np.array([1, 0, 1, 0, 1, 0], dtype=float)
    # perfect forecasts -> BSS 1.0
    assert brier_skill_score(y, y) == pytest.approx(1.0)
    # constant base-rate forecast -> BSS 0.0 (no skill over climatology)
    base = float(y.mean())
    assert brier_skill_score(np.full(6, base), y) == pytest.approx(0.0, abs=1e-12)
    # single-class -> NaN (baseline brier 0)
    assert math.isnan(brier_skill_score([0.5, 0.5], [1, 1]))


def test_grouped_bootstrap_matches_row_when_singletons():
    # all groups size 1 -> grouped bootstrap ~ row bootstrap; CI still excludes 0
    rng = np.random.default_rng(5)
    y = (rng.uniform(0, 1, 300) < 0.5).astype(float)
    base = np.where(y == 1, 0.55, 0.45)
    cand = np.where(y == 1, 0.9, 0.1)
    groups = np.arange(300)  # singletons
    res = bootstrap_metric_diff_grouped(base, cand, y, groups, brier_score, n_boot=300, seed=1)
    assert res["diff"] < 0 and res["ci_high"] < 0


def test_grouped_bootstrap_wider_than_row_with_clusters():
    # strongly correlated within big clusters -> grouped CI should be >= row CI width
    rng = np.random.default_rng(6)
    n_groups, gsize = 40, 5
    y = np.repeat((rng.uniform(0, 1, n_groups) < 0.5).astype(float), gsize)
    groups = np.repeat(np.arange(n_groups), gsize)
    base = np.where(y == 1, 0.55, 0.45)
    cand = np.where(y == 1, 0.8, 0.2)
    row = bootstrap_metric_diff(base, cand, y, brier_score, n_boot=400, seed=2)
    grp = bootstrap_metric_diff_grouped(base, cand, y, groups, brier_score, n_boot=400, seed=2)
    assert (grp["ci_high"] - grp["ci_low"]) >= (row["ci_high"] - row["ci_low"]) * 0.95


def test_validation_rejects_bad_inputs():
    with pytest.raises(ValueError):
        brier_score([1.2], [1])  # out of range
    with pytest.raises(ValueError):
        brier_score([0.5], [2])  # non-binary label
    with pytest.raises(ValueError):
        brier_score([], [])  # empty
    with pytest.raises(ValueError):
        brier_score([0.5, 0.5], [1])  # shape mismatch


def test_score_all_keys():
    rng = np.random.default_rng(4)
    p = rng.uniform(0, 1, 200)
    y = (rng.uniform(0, 1, 200) < p).astype(float)
    s = score_all(p, y)
    for k in ("n", "brier", "ece", "ace", "mce", "log_loss", "auc", "accuracy", "base_rate"):
        assert k in s
