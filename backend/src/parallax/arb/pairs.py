"""Pairing one Kalshi market with one Polymarket market — carefully.

"Same event" is not the same as "same payout", and the gap between those two
is where a cross-venue arbitrage quietly turns into an unhedged directional
bet. Two markets on the same headline can still differ on:

- **Polarity** — which side of each venue's contract corresponds to the same
  real-world outcome.
- **Deadline** — the exact settlement instant, and the timezone it is stated
  in. "By end of 2026" is not one date.
- **Resolution source** — whose number decides it, and what happens when that
  source revises.
- **Void rules** — if one venue can cancel and refund while the other settles,
  the "hedge" pays out on one leg only.

So a pair is inert until a human has read both rule sets and recorded that
review here. `MarketPair.reviewed` gates the scanner: an unreviewed pair is
never scanned, because basis risk reported as arbitrage is worse than no
signal at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from parallax.arb.venue import OutcomeRef


class UnreviewedPairError(RuntimeError):
    """Raised when a pair is scanned before its settlement terms were reviewed."""


@dataclass(frozen=True)
class MarketPair:
    """Two outcomes asserted — by a named human — to have identical payouts.

    The assertion is: if `yes_leg` settles to 1, `no_leg` settles to 0, and
    vice versa, with no state of the world in which both pay or neither pays.
    Holding one of each is then a locked package worth exactly $1.00.
    """

    name: str
    yes_leg: OutcomeRef
    no_leg: OutcomeRef

    # --- settlement equivalence, recorded explicitly ---
    deadline: datetime
    """The settlement instant both legs must share. Timezone-aware, always."""

    resolution_source: str
    """Whose published number decides both legs."""

    void_rules: str
    """What each venue does on cancellation, and whether those agree."""

    reviewed: bool = False
    """True only after a human read both rule sets end to end."""

    reviewed_by: str | None = None
    reviewed_on: date | None = None
    notes: str = ""

    known_differences: tuple[str, ...] = field(default_factory=tuple)
    """Differences found during review and accepted anyway. Each one is basis
    risk that the scanner's profit number does not capture."""

    def require_reviewed(self) -> None:
        if not self.reviewed:
            raise UnreviewedPairError(
                f"pair {self.name!r} has not had its settlement terms reviewed; "
                "set reviewed=True with reviewed_by/reviewed_on once both venues' "
                "rules have been read and confirmed equivalent"
            )

    @property
    def deadline_is_tz_aware(self) -> bool:
        return self.deadline.tzinfo is not None


REGISTRY: dict[str, MarketPair] = {}
"""Reviewed pairs, keyed by name. Deliberately empty: every entry has to be
earned by reading two rule books, and seeding it with plausible-looking
examples would invite someone to trade an unreviewed mapping."""


def register(pair: MarketPair) -> MarketPair:
    """Add a pair to the registry, refusing unreviewed or naive-deadline entries."""
    pair.require_reviewed()
    if not pair.deadline_is_tz_aware:
        raise ValueError(f"pair {pair.name!r} deadline must be timezone-aware")
    REGISTRY[pair.name] = pair
    return pair
