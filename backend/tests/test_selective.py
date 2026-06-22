"""Tests for selective-prediction metrics (risk-coverage, AURC, operating point)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from parallax.scoring.selective import (
    apply_threshold,
    aurc,
    confidence,
    coverage_at_error,
    operating_threshold,
    risk_coverage_curve,
    selective_at_confidence,
)


def test_confidence():
    np.testing.assert_allclose(confidence([0.9, 0.1, 0.5, 0.7]), [0.9, 0.9, 0.5, 0.7])


def test_selective_at_confidence_basic():
    # confidences: 0.95,0.9,0.6,0.55 ; preds 1,0,1,0 ; labels 1,0,0,1
    p = np.array([0.95, 0.10, 0.60, 0.45])
    y = np.array([1, 0, 0, 1])
    sp = selective_at_confidence(p, y, 0.9)  # accepts first two (conf .95,.90)
    assert sp.n_covered == 2
    assert sp.coverage == pytest.approx(0.5)
    assert sp.realized_error == pytest.approx(0.0)  # both correct
    assert sp.promised_error == pytest.approx(0.1)


def test_selective_at_confidence_none_covered():
    sp = selective_at_confidence([0.6, 0.55], [1, 0], 0.99)
    assert sp.n_covered == 0 and math.isnan(sp.realized_error)


def test_risk_coverage_perfect_ranking():
    # all errors are on the least-confident items -> risk rises only at the end
    p = np.array([0.99, 0.95, 0.90, 0.51])  # preds all 1
    y = np.array([1, 1, 1, 0])              # only last (least confident) is wrong
    cov, risk = risk_coverage_curve(p, y)
    assert risk[0] == 0.0 and risk[1] == 0.0 and risk[2] == 0.0
    assert risk[-1] == pytest.approx(0.25)
    assert aurc(p, y) < 0.1  # good ranking -> low area


def test_operating_threshold_and_apply_oos():
    # Train: confident items correct, unconfident wrong -> threshold should exclude tail
    ptr = np.array([0.99, 0.95, 0.90, 0.52, 0.51])
    ytr = np.array([1, 1, 1, 0, 0])  # two least-confident wrong (preds all 1)
    thr = operating_threshold(ptr, ytr, target_error=0.0)
    # at 0 error we can accept the top 3 (0.90..0.99); threshold ~0.90
    assert thr == pytest.approx(0.90)
    # apply to a test set
    pte = np.array([0.97, 0.93, 0.60])
    yte = np.array([1, 0, 0])
    res = apply_threshold(pte, yte, thr)
    assert res["n_covered"] == 2  # 0.97 and 0.93 clear 0.90
    assert res["realized_error"] == pytest.approx(0.5)  # the 0.93->pred1 vs y0 is wrong


def test_operating_threshold_tie_safe():
    # 0.99 correct anchor + ten 0.7s (first five right, last five wrong). A
    # prefix-index cutoff would return 0.7 and then conf>=0.7 admits the wrong
    # tie members -> realized error 0.45. Tie-safe must return 0.99 (realized 0).
    p = np.array([0.99] + [0.7] * 10)
    y = np.array([1] + [1] * 5 + [0] * 5, dtype=float)
    thr = operating_threshold(p, y, target_error=0.0)
    res = apply_threshold(p, y, thr)
    assert res["n_covered"] == 1
    assert res["realized_error"] <= 1e-9


def test_aurc_nan_single():
    assert math.isnan(aurc([0.9], [1]))
    assert math.isnan(aurc([0.9], [0]))


def test_operating_threshold_unachievable():
    # most-confident item is wrong; target 0 impossible -> inf (accept nothing)
    assert operating_threshold([0.99, 0.6], [0, 1], target_error=0.0) == float("inf")
    res = apply_threshold([0.99], [0], float("inf"))
    assert res["n_covered"] == 0


def test_coverage_at_error_monotone_help():
    rng = np.random.default_rng(0)
    # confidence correlated with correctness -> coverage_at_error > 0 for small tau
    truth = rng.uniform(0, 1, 1000)
    p = np.clip(truth, 0.01, 0.99)
    y = (rng.uniform(0, 1, 1000) < truth).astype(float)
    res = coverage_at_error(p, y, 0.1)
    assert res["coverage"] > 0.0
    assert res["realized_error"] <= 0.1 + 1e-9
