# Approximate token costs (USD per 1K tokens)
# Updated per validation: Haiku ~$0.005/call, Sonnet ~$0.031/call
_PRICING = {
    "haiku": {"input": 0.001, "output": 0.005},
    "sonnet": {"input": 0.003, "output": 0.015},
    "opus": {"input": 0.015, "output": 0.075},
}


class BudgetTracker:
    """Tracks daily token spend and enforces budget caps.

    $20/day cap provides ~6.5x headroom over expected daily spend.
    Auto-degrades to rule-based when budget is exceeded.
    """

    def __init__(self, daily_cap_usd: float) -> None:
        self._daily_cap = daily_cap_usd
        self._spend_today: float = 0.0
        self._last_activation: dict[str, int] = {}  # agent_id -> tick
        self._call_count: int = 0

    def record(self, input_tokens: int, output_tokens: int, model: str) -> None:
        pricing = _PRICING.get(model, _PRICING["sonnet"])
        cost = (input_tokens / 1000) * pricing["input"] + (output_tokens / 1000) * pricing["output"]
        self._spend_today += cost
        self._call_count += 1

    def total_spend_today(self) -> float:
        return self._spend_today

    def is_over_budget(self) -> bool:
        return self._spend_today >= self._daily_cap

    def reset_daily(self) -> None:
        self._spend_today = 0.0
        self._call_count = 0

    def record_activation(self, agent_id: str, tick: int) -> None:
        self._last_activation[agent_id] = tick

    def can_activate(self, agent_id: str, current_tick: int, cooldown_ticks: int) -> bool:
        last = self._last_activation.get(agent_id)
        if last is None:
            return True
        return current_tick - last >= cooldown_ticks

    def stats(self) -> dict:
        return {
            "spend_today_usd": self._spend_today,
            "daily_cap_usd": self._daily_cap,
            "utilization_pct": (self._spend_today / self._daily_cap * 100) if self._daily_cap > 0 else 0,
            "call_count": self._call_count,
            "is_over_budget": self.is_over_budget(),
        }
