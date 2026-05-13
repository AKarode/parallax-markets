"""Historical crisis context injected into prediction model prompts.

Claude's training data cuts off ~August 2025. The Iran-Hormuz crisis began
February 2026. Without this context, the models are predicting blind about
events they have zero knowledge of. This module provides a structured timeline
that gets prepended to every prediction prompt.

The context can be rendered from the crisis_events DB table or from the
hardcoded SEED_EVENTS list as a fallback. Context staleness is tracked via
context_age_hours for downstream confidence penalties.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

logger = logging.getLogger(__name__)

SEED_EVENTS = [
    {"event_time": "2025-06-01T00:00:00Z", "headline": "Failed nuclear negotiations between Iran and the US in Geneva", "source": "seed", "category": "diplomacy"},
    {"event_time": "2025-06-15T00:00:00Z", "headline": "Brief 12-day US air conflict with Iran begins", "source": "seed", "category": "military"},
    {"event_time": "2025-12-15T00:00:00Z", "headline": "Iran accelerates uranium enrichment amid escalating tensions", "source": "seed", "category": "nuclear"},
    {"event_time": "2026-02-06T00:00:00Z", "headline": "Iran and US hold indirect nuclear talks in Oman's capital Muscat", "source": "seed", "category": "diplomacy"},
    {"event_time": "2026-02-15T00:00:00Z", "headline": "Iran triples oil exports and draws down storage anticipating disruption", "source": "seed", "category": "oil"},
    {"event_time": "2026-02-27T00:00:00Z", "headline": "Omani FM announces breakthrough - Iran agrees to halt enriched uranium stockpiling", "source": "seed", "category": "diplomacy"},
    {"event_time": "2026-02-28T00:00:00Z", "headline": "US and Israel launch coordinated air strikes across Iran; Supreme Leader Khamenei killed", "source": "seed", "category": "military"},
    {"event_time": "2026-02-28T12:00:00Z", "headline": "Iran announces closure of Strait of Hormuz in retaliation; IRGC attacks merchant ships", "source": "seed", "category": "hormuz"},
    {"event_time": "2026-03-02T00:00:00Z", "headline": "IRGC officially confirms Strait of Hormuz closed; Brent crude surges from ~$72 to $82", "source": "seed", "category": "hormuz"},
    {"event_time": "2026-03-04T00:00:00Z", "headline": "Strait fully blocked; oil/LNG exports stranded; Brent breaks $120", "source": "seed", "category": "oil"},
    {"event_time": "2026-03-09T00:00:00Z", "headline": "Brent hits $119.50 session high; WTI posts biggest weekly gain in history (+35.6%)", "source": "seed", "category": "oil"},
    {"event_time": "2026-03-19T00:00:00Z", "headline": "US begins aerial campaign against Iranian naval targets to forcibly reopen Hormuz", "source": "seed", "category": "military"},
    {"event_time": "2026-03-21T00:00:00Z", "headline": "Trump issues 48-hour ultimatum to Iran", "source": "seed", "category": "diplomacy"},
    {"event_time": "2026-03-23T00:00:00Z", "headline": "Oil drops ~11% after Trump pauses strikes on Iran energy infrastructure", "source": "seed", "category": "oil"},
    {"event_time": "2026-03-26T00:00:00Z", "headline": "Israeli airstrike kills IRGC Navy Commander Tangsiri", "source": "seed", "category": "military"},
    {"event_time": "2026-03-28T00:00:00Z", "headline": "Houthis enter the war - launch ballistic missile toward Israel", "source": "seed", "category": "military"},
    {"event_time": "2026-03-31T00:00:00Z", "headline": "Kuwaiti VLCC Al Salmi struck by Iranian drone at Port of Dubai", "source": "seed", "category": "hormuz"},
    {"event_time": "2026-04-03T00:00:00Z", "headline": "US F-15E shot down over Iran; second US plane crashes near Hormuz", "source": "seed", "category": "military"},
    {"event_time": "2026-04-04T00:00:00Z", "headline": "Trump issues 48-hour ultimatum; Israel strikes Iran's largest petrochemical complex at Asaluyeh", "source": "seed", "category": "military"},
    {"event_time": "2026-04-05T00:00:00Z", "headline": "Iran strikes BAPCO oil refinery in Bahrain; drones hit Kuwaiti power/desalination plants", "source": "seed", "category": "military"},
    {"event_time": "2026-04-07T00:00:00Z", "headline": "CEASEFIRE AGREED 2 hours before Trump's deadline; Brent crashes 13% to ~$95", "source": "seed", "category": "ceasefire"},
    {"event_time": "2026-04-08T00:00:00Z", "headline": "Ceasefire in effect BUT Israel strikes Lebanon same day; little Hormuz reopening", "source": "seed", "category": "ceasefire"},
    {"event_time": "2026-04-09T00:00:00Z", "headline": "Hormuz remains effectively closed; only 8 ships in 2 days vs 100+/day pre-war", "source": "seed", "category": "hormuz"},
    {"event_time": "2026-04-11T00:00:00Z", "headline": "Islamabad talks begin; VP Vance + Witkoff + Kushner in 21+ hour marathon session", "source": "seed", "category": "diplomacy"},
    {"event_time": "2026-04-12T00:00:00Z", "headline": "TALKS FAIL - Vance: Iranians have chosen not to accept our terms; ceasefire continues through ~April 21", "source": "seed", "category": "diplomacy"},
]

CRISIS_TIMELINE = """
## CRITICAL CONTEXT — You must read this carefully before making any predictions.

Your training data ends around August 2025. The following events have occurred
AFTER your knowledge cutoff. This is not hypothetical — these are real events
that have already happened.

### Background: 2025 Iran-US Tensions
- Mid-2025: Failed nuclear negotiations between Iran and the US in Geneva.
- June 2025: Brief 12-day US air conflict with Iran. Oil markets shrugged it
  off — Brent stayed below $70. Iran's Strait of Hormuz remained open.
- Late 2025: Tensions continued to escalate. Iran accelerated uranium
  enrichment.

### February 2026: War Begins
- Feb 6: Iran and US held indirect nuclear talks in Oman's capital Muscat.
- Feb 15-20: Iran tripled oil exports and drew down storage, anticipating
  disruption.
- Feb 27: Omani FM announced a "breakthrough" — Iran agreed to halt enriched
  uranium stockpiling and accept IAEA verification.
- **Feb 28: US and Israel launched coordinated air strikes across Iran. Supreme
  Leader Ali Khamenei was killed.** Iran retaliated with missiles and drones on
  Israel, US bases, and Gulf allies.
- **Feb 28: Iran announced closure of Strait of Hormuz in retaliation.** IRGC
  began attacking merchant ships and laying sea mines.

### March 2026: Hormuz Blockade & Oil Shock
- Mar 2: IRGC officially confirmed Strait of Hormuz closed. Threatened to set
  fire to any ship entering. Brent crude surged from ~$72 to $82 (+13%).
- Mar 4: Strait fully blocked. Oil/LNG exports stranded. Brent broke $120.
- Mar 9: Brent hit $119.50 session high. WTI posted biggest weekly gain in
  history (+35.6%). Trump falsely claimed strait had reopened.
- Mar 15: Trump demanded NATO and China help reopen the strait.
- Mar 19: US began aerial campaign against Iranian naval targets to forcibly
  reopen Hormuz.
- Mar 21: Trump issued 48-hour ultimatum to Iran. Iran doubled down, threatening
  to strike Gulf desalination plants and power infrastructure.
- Mar 23: Oil dropped ~11% after Trump paused strikes on Iran energy
  infrastructure for 5 days.
- Mar 25: Pakistan delivered US "15-point proposal" to Iran: end nuclear program,
  reopen Hormuz, limit missiles, restrict armed groups, in exchange for sanctions
  relief. Iran rejected it.
- Mar 26-27: Israeli airstrike killed IRGC Navy Commander Tangsiri (directly
  responsible for Hormuz closure).
- Mar 28: Houthis entered the war — launched ballistic missile toward Israel.
  2,500 US Marines deployed for Hormuz operations.
- Mar 31: Kuwaiti VLCC Al Salmi struck by Iranian drone at Port of Dubai. WSJ:
  Trump admin concludes military Hormuz reopening would take too long — shifting
  to diplomacy. Brent-WTI spread peaked at $25/bbl.

### April 2026: Ceasefire & Fragile Negotiations
- Apr 1: Trump claims Iran requested ceasefire — Iran FM calls it "false."
- Apr 2: UK-led 40-nation conference on Hormuz. Iran tightens blockade further,
  drops shipping to 10-20 ships/day from 150.
- **Apr 3: US F-15E shot down over Iran (pilot rescued, WSO missing 48hrs).
  Second US plane crashes near Hormuz. Iran hits Gulf refineries.** War costs
  becoming tangible for the US. Brent $112.
- **Apr 4: Trump issues 48-hour ultimatum: "all Hell will reign down." Israel
  strikes Iran's largest petrochemical complex at Asaluyeh (inoperable).**
- **Apr 5: Iran retaliates — strikes BAPCO oil refinery in Bahrain, drones hit
  Kuwaiti power/desalination plants. 45-day ceasefire proposed by mediators;
  Iran REJECTS it, demanding permanent end to war.**
- Apr 6: Iran FM: "We won't merely accept a ceasefire." Trump: deadline is
  "final." Brent $111.
- **Apr 7: CEASEFIRE AGREED 2 hours before Trump's deadline.** Dated Brent hit
  ALL-TIME RECORD $144.42 BEFORE announcement, then crashed 13% to ~$95. At
  least 50 new Polymarket accounts made large ceasefire bets minutes before
  — suspected insider trading.
- **Apr 8: Ceasefire in effect BUT Israel strikes Lebanon same day. Iran calls it
  "grave violation." Little Hormuz reopening.** Dated Brent spot $124.68 vs
  futures $93.76 — massive physical/paper divergence.
- **Apr 9: Hormuz remains "effectively closed." Only 8 ships in 2 days vs
  100+/day pre-war. Iran charging $1M+ tolls. Iran blocks Chinese ships. 230
  loaded tankers trapped.** Brent $101.
- Apr 10: Iranian delegates arrive in Islamabad. White House warns staff over
  prediction market bets. Brent $97.
- **Apr 11: Islamabad talks begin. VP Vance + Witkoff + Kushner in 21+ hour
  marathon session. Trump says US forces "clearing" Hormuz.** Brent ~$98.
- **Apr 12 (today): TALKS FAIL. Vance: "Iranians have chosen not to accept our
  terms." Sticking points: Lebanon, sanctions, guarantees. Ceasefire continues
  through ~April 21 but no deal.** Brent ~$98, expected to gap up Monday.

### Current Market State (as of Apr 12, 2026)
- **Strait of Hormuz: effectively closed.** Iran charging tolls, limiting
  traffic to a trickle.
- **Ceasefire: fragile, 10 days remaining.** No formal agreement. Talks ongoing
  but stalled.

### Prediction Market Contracts
- **KXUSAIRANAGREEMENT**: "Will the US and Iran reach a formal agreement?" Resolves YES on a SIGNED DEAL (not just ceasefire). Historical precedent: JCPOA took 2+ years of formal negotiations.
- **KXCLOSEHORMUZ**: "Will Iran close Strait of Hormuz for 7+ days?" Already settled YES. Sub-contracts on reopening timing.
- **KXWTIMAX/KXWTIMIN**: Oil price range contracts. WTI max/min thresholds for year-end.
"""


@dataclass
class CrisisContextResult:
    """Result of rendering crisis context with metadata."""

    context: str
    context_age_hours: float
    event_count: int
    latest_event_time: datetime | None
    is_from_db: bool


def seed_crisis_events(conn: duckdb.DuckDBPyConnection) -> int:
    """Seed the crisis_events table with hardcoded events if empty.

    Returns:
        Number of events seeded.
    """
    from parallax.ingestion.crisis_ingester import CrisisIngester

    ingester = CrisisIngester(conn)
    if ingester.get_event_count() > 0:
        logger.debug("crisis_events table already populated, skipping seed")
        return 0

    return ingester.ingest_from_dict(SEED_EVENTS, category="seed")


def compute_staleness_penalty(context_age_hours: float) -> float:
    """Compute confidence penalty based on context staleness.

    If context_age_hours > 24, apply confidence penalty of min(1, 1 - (age_hours - 24) / 48).
    This means:
    - 0-24 hours: no penalty (1.0)
    - 24-72 hours: linear decay from 1.0 to 0.0
    - 72+ hours: zero confidence (0.0)

    Returns:
        Confidence multiplier between 0.0 and 1.0.
    """
    if context_age_hours <= 24:
        return 1.0
    penalty = 1.0 - (context_age_hours - 24) / 48
    return max(0.0, min(1.0, penalty))


def render_crisis_context_from_db(
    conn: duckdb.DuckDBPyConnection,
    lookback_days: int = 21,
) -> CrisisContextResult:
    """Render crisis context from the crisis_events DB table.

    Args:
        conn: DuckDB connection.
        lookback_days: Number of days of events to include.

    Returns:
        CrisisContextResult with rendered context and metadata.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=lookback_days)

    rows = conn.execute(
        """
        SELECT event_time, headline, source, category
        FROM crisis_events
        WHERE event_time >= ?
        ORDER BY event_time DESC
        """,
        [cutoff],
    ).fetchall()

    if not rows:
        return CrisisContextResult(
            context="",
            context_age_hours=float("inf"),
            event_count=0,
            latest_event_time=None,
            is_from_db=True,
        )

    latest_event_time = rows[0][0]
    if latest_event_time.tzinfo is None:
        latest_event_time = latest_event_time.replace(tzinfo=timezone.utc)

    context_age_hours = (now - latest_event_time).total_seconds() / 3600

    lines = [
        "## CRISIS TIMELINE (from database)",
        f"**Context age: {context_age_hours:.1f} hours since latest event**",
        "",
    ]

    current_date = None
    for event_time, headline, source, category in rows:
        event_date = event_time.strftime("%Y-%m-%d")
        if event_date != current_date:
            current_date = event_date
            lines.append(f"### {event_date}")

        category_tag = f"[{category}]" if category else ""
        lines.append(f"- {event_time.strftime('%H:%M')}: {headline} {category_tag}")

    context = "\n".join(lines)

    return CrisisContextResult(
        context=context,
        context_age_hours=context_age_hours,
        event_count=len(rows),
        latest_event_time=latest_event_time,
        is_from_db=True,
    )


def get_crisis_context(conn: duckdb.DuckDBPyConnection | None = None) -> str:
    """Return the full crisis context for prompt injection.

    If a DB connection is provided and has events, renders from the DB.
    Otherwise falls back to the hardcoded CRISIS_TIMELINE.

    Args:
        conn: Optional DuckDB connection.

    Returns:
        Crisis context string for LLM prompt injection.
    """
    if conn is not None:
        try:
            result = render_crisis_context_from_db(conn)
            if result.event_count > 0:
                return result.context
        except Exception:
            logger.exception("Failed to render crisis context from DB, using fallback")

    return CRISIS_TIMELINE


def _latest_seed_event_time() -> datetime:
    """Return the most recent ``event_time`` from ``SEED_EVENTS``.

    Used so the hardcoded fallback context reports a real age in hours rather
    than pretending to be fresh (which would let downstream confidence shrink
    skip the staleness penalty entirely on the day the DB ingest is broken).
    """
    latest: datetime | None = None
    for event in SEED_EVENTS:
        raw = event["event_time"]
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if latest is None or parsed > latest:
            latest = parsed
    assert latest is not None, "SEED_EVENTS is empty"
    return latest


def get_crisis_context_with_metadata(
    conn: duckdb.DuckDBPyConnection | None = None,
) -> CrisisContextResult:
    """Return crisis context with metadata including staleness.

    When falling back to ``CRISIS_TIMELINE`` (DB empty or unavailable), the
    reported ``context_age_hours`` is computed from the latest ``SEED_EVENTS``
    entry, NOT 0.0 — otherwise downstream code that applies the staleness
    penalty would treat the hardcoded fallback as fresh on a day when the
    crisis ingester has fallen behind. The result's ``is_from_db`` flag lets
    callers in a "live" data environment fire an alert when this fallback
    triggered (the crisis ingester is probably broken).

    Args:
        conn: Optional DuckDB connection.

    Returns:
        CrisisContextResult with context string and metadata.
    """
    if conn is not None:
        try:
            result = render_crisis_context_from_db(conn)
            if result.event_count > 0:
                return result
        except Exception:
            logger.exception("Failed to render crisis context from DB, using fallback")

    latest_seed = _latest_seed_event_time()
    age_hours = (datetime.now(timezone.utc) - latest_seed).total_seconds() / 3600
    return CrisisContextResult(
        context=CRISIS_TIMELINE,
        context_age_hours=age_hours,
        event_count=len(SEED_EVENTS),
        latest_event_time=latest_seed,
        is_from_db=False,
    )
