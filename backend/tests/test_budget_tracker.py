from parallax.budget.tracker import BudgetTracker


def test_initial_spend_is_zero():
    tracker = BudgetTracker(daily_cap_usd=20.0)
    assert tracker.total_spend_today() == 0.0
    assert tracker.is_over_budget() is False


def test_record_spend():
    tracker = BudgetTracker(daily_cap_usd=20.0)
    tracker.record(input_tokens=4000, output_tokens=500, model="haiku")
    assert tracker.total_spend_today() > 0.0


def test_over_budget_triggers():
    tracker = BudgetTracker(daily_cap_usd=0.001)  # Tiny budget
    tracker.record(input_tokens=100000, output_tokens=10000, model="sonnet")
    assert tracker.is_over_budget() is True


def test_cooldown_enforcement():
    tracker = BudgetTracker(daily_cap_usd=20.0)
    tracker.record_activation("iran/irgc_navy", tick=10)

    assert tracker.can_activate("iran/irgc_navy", current_tick=10, cooldown_ticks=2) is False
    assert tracker.can_activate("iran/irgc_navy", current_tick=12, cooldown_ticks=2) is True
    # Different agent unaffected
    assert tracker.can_activate("usa/centcom", current_tick=10, cooldown_ticks=2) is True


def test_reset_daily():
    tracker = BudgetTracker(daily_cap_usd=20.0)
    tracker.record(input_tokens=10000, output_tokens=1000, model="sonnet")
    assert tracker.total_spend_today() > 0.0
    tracker.reset_daily()
    assert tracker.total_spend_today() == 0.0


def test_stats():
    tracker = BudgetTracker(daily_cap_usd=20.0)
    tracker.record(input_tokens=4000, output_tokens=500, model="haiku")
    stats = tracker.stats()
    assert stats["daily_cap_usd"] == 20.0
    assert stats["spend_today_usd"] > 0.0
    assert stats["call_count"] == 1
    assert stats["is_over_budget"] is False


def test_haiku_cost_approximation():
    """Verify Haiku costs approximately $0.005 per typical call (4K in, 500 out)."""
    tracker = BudgetTracker(daily_cap_usd=20.0)
    tracker.record(input_tokens=4000, output_tokens=500, model="haiku")
    cost = tracker.total_spend_today()
    # 4000/1000 * 0.001 + 500/1000 * 0.005 = 0.004 + 0.0025 = 0.0065
    assert 0.005 <= cost <= 0.008


def test_sonnet_cost_approximation():
    """Verify Sonnet costs approximately $0.031 per typical call (8K in, 1K out)."""
    tracker = BudgetTracker(daily_cap_usd=20.0)
    tracker.record(input_tokens=8000, output_tokens=1000, model="sonnet")
    cost = tracker.total_spend_today()
    # 8000/1000 * 0.003 + 1000/1000 * 0.015 = 0.024 + 0.015 = 0.039
    assert 0.030 <= cost <= 0.045
