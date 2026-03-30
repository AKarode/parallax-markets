from parallax.simulation.circuit_breaker import CircuitBreaker


def test_allows_single_level_escalation():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    assert cb.allow_escalation("iran/irgc_navy", levels=1, goldstein_score=None) is True


def test_blocks_multi_level_escalation():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    assert cb.allow_escalation("iran/irgc_navy", levels=3, goldstein_score=None) is False


def test_cooldown_blocks_after_escalation():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    cb.record_escalation("iran/irgc_navy", tick=10)

    assert cb.allow_escalation(
        "iran/irgc_navy", levels=1, goldstein_score=None, current_tick=11
    ) is False
    assert cb.allow_escalation(
        "iran/irgc_navy", levels=1, goldstein_score=None, current_tick=12
    ) is False
    assert cb.allow_escalation(
        "iran/irgc_navy", levels=1, goldstein_score=None, current_tick=13
    ) is True


def test_exogenous_shock_bypasses_all_limits():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    cb.record_escalation("iran/irgc_navy", tick=10)

    # Normally blocked (cooldown + multi-level), but goldstein > threshold
    assert cb.allow_escalation(
        "iran/irgc_navy", levels=5, goldstein_score=9.5, current_tick=11
    ) is True


def test_different_agents_independent_cooldowns():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    cb.record_escalation("iran/irgc_navy", tick=10)

    # Different agent should not be blocked
    assert cb.allow_escalation(
        "usa/centcom", levels=1, goldstein_score=None, current_tick=11
    ) is True


def test_reality_anchor_within_range():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)

    # Price within historical range passes
    assert cb.reality_check("oil_price", 120.0, floor=30.0, ceiling=200.0) is True


def test_reality_anchor_above_ceiling():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)

    # Price above ceiling fails
    assert cb.reality_check("oil_price", 250.0, floor=30.0, ceiling=200.0) is False


def test_reality_anchor_below_floor():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)

    assert cb.reality_check("oil_price", 10.0, floor=30.0, ceiling=200.0) is False


def test_reality_anchor_clamp():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)

    # Clamp to ceiling
    assert cb.clamp("oil_price", 250.0, floor=30.0, ceiling=200.0) == 200.0
    # Clamp to floor
    assert cb.clamp("oil_price", 10.0, floor=30.0, ceiling=200.0) == 30.0
    # Within range, unchanged
    assert cb.clamp("oil_price", 120.0, floor=30.0, ceiling=200.0) == 120.0


def test_negative_goldstein_absolute_value():
    """Negative goldstein scores should use absolute value for threshold check."""
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    cb.record_escalation("iran/irgc_navy", tick=10)

    # -9.5 absolute value is 9.5 >= 8.0, should bypass
    assert cb.allow_escalation(
        "iran/irgc_navy", levels=5, goldstein_score=-9.5, current_tick=11
    ) is True


def test_goldstein_below_threshold_does_not_bypass():
    cb = CircuitBreaker(max_per_tick=1, cooldown_ticks=3, shock_threshold=8.0)
    cb.record_escalation("iran/irgc_navy", tick=10)

    # 5.0 < 8.0 threshold, should NOT bypass cooldown
    assert cb.allow_escalation(
        "iran/irgc_navy", levels=1, goldstein_score=5.0, current_tick=11
    ) is False
