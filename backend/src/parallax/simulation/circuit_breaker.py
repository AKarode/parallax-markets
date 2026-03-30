"""Circuit breaker for simulation escalation control.

Prevents runaway escalation by enforcing:
- Max 1 escalation level per tick for agent-initiated actions
- 3-tick cooldown after major escalation (per agent)
- Exogenous shock override: real-world events with high Goldstein scores bypass the breaker
- Reality anchor: outputs sanity-checked against historical ranges
"""


class CircuitBreaker:
    """Controls escalation velocity and enforces reality bounds."""

    def __init__(
        self,
        max_per_tick: int,
        cooldown_ticks: int,
        shock_threshold: float,
    ) -> None:
        self._max_per_tick = max_per_tick
        self._cooldown_ticks = cooldown_ticks
        self._shock_threshold = shock_threshold
        self._last_escalation: dict[str, int] = {}  # agent_id -> tick

    def allow_escalation(
        self,
        agent_id: str,
        levels: int,
        goldstein_score: float | None,
        current_tick: int = 0,
    ) -> bool:
        """Check whether an escalation action is permitted.

        Args:
            agent_id: The agent requesting the escalation.
            levels: Number of escalation levels requested.
            goldstein_score: Goldstein scale score from a real-world event,
                or None for agent-initiated actions.
            current_tick: Current simulation tick.

        Returns:
            True if the escalation is allowed.
        """
        # Exogenous shock override -- bypass all limits
        if goldstein_score is not None and abs(goldstein_score) >= self._shock_threshold:
            return True

        # Check escalation level limit
        if levels > self._max_per_tick:
            return False

        # Check cooldown
        last_tick = self._last_escalation.get(agent_id)
        if last_tick is not None:
            if current_tick - last_tick < self._cooldown_ticks:
                return False

        return True

    def record_escalation(self, agent_id: str, tick: int) -> None:
        """Record that an agent escalated at the given tick."""
        self._last_escalation[agent_id] = tick

    # --- Reality Anchor ---

    def reality_check(
        self,
        metric: str,
        value: float,
        floor: float,
        ceiling: float,
    ) -> bool:
        """Check if a value falls within historically plausible bounds.

        Args:
            metric: Name of the metric (for logging).
            value: The value to check.
            floor: Lower bound of historical range.
            ceiling: Upper bound of historical range.

        Returns:
            True if value is within [floor, ceiling].
        """
        return floor <= value <= ceiling

    def clamp(
        self,
        metric: str,
        value: float,
        floor: float,
        ceiling: float,
    ) -> float:
        """Clamp a value to historically plausible bounds.

        Args:
            metric: Name of the metric (for logging).
            value: The value to clamp.
            floor: Lower bound.
            ceiling: Upper bound.

        Returns:
            Value clamped to [floor, ceiling].
        """
        return max(floor, min(ceiling, value))
