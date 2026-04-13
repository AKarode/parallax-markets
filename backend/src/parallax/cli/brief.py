"""Daily intelligence brief with executable quote semantics and trade journaling."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from parallax.budget.tracker import BudgetTracker
from parallax.contracts.mapping_policy import MappingPolicy
from parallax.contracts.registry import ContractRegistry
from parallax.db.runtime import RuntimeConfig, resolve_runtime_config
from parallax.db.schema import create_tables
from parallax.markets.kalshi import IRAN_EVENT_TICKERS, KalshiClient
from parallax.markets.polymarket import PolymarketClient
from parallax.markets.schemas import MarketPrice
from parallax.prediction.ceasefire import CeasefirePredictor
from parallax.prediction.hormuz import HormuzReopeningPredictor
from parallax.prediction.oil_price import OilPricePredictor
from parallax.prediction.schemas import PredictionOutput
from parallax.config.risk import load_risk_limits
from parallax.portfolio.allocator import PortfolioAllocator
from parallax.portfolio.schemas import PortfolioState, ProposedTrade
from parallax.scoring.ledger import SignalLedger
from parallax.scoring.prediction_log import PredictionLogger
from parallax.scoring.recalibration import recalibrate_probability
from parallax.scoring.tracker import PaperTradeTracker
from parallax.simulation.cascade import CascadeEngine
from parallax.simulation.config import ScenarioConfig, load_scenario_config
from parallax.simulation.world_state import WorldState

logger = logging.getLogger(__name__)

SCENARIO_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "scenario_hormuz.yaml"


def _persist_run_start(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    runtime,
) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_id, started_at, status, data_environment, execution_environment)
        VALUES (?, ?, 'running', ?, ?)
        """,
        [run_id, datetime.now(timezone.utc), runtime.data_environment, runtime.execution_environment],
    )


def _persist_run_end(
    conn: duckdb.DuckDBPyConnection,
    run_id: str,
    *,
    status: str = "completed",
    error: str | None = None,
    predictions_count: int = 0,
    signals_count: int = 0,
    trades_count: int = 0,
) -> None:
    conn.execute(
        """
        UPDATE runs
        SET ended_at = ?, status = ?, error = ?,
            predictions_count = ?, signals_count = ?, trades_count = ?
        WHERE run_id = ?
        """,
        [
            datetime.now(timezone.utc),
            status,
            error,
            predictions_count,
            signals_count,
            trades_count,
            run_id,
        ],
    )


def _make_dry_run_predictions() -> list[PredictionOutput]:
    now = datetime.now(timezone.utc)
    return [
        PredictionOutput(
            model_id="oil_price",
            prediction_type="oil_price_direction",
            probability=0.72,
            direction="increase",
            magnitude_range=[3.0, 8.0],
            unit="USD/bbl",
            timeframe="7d",
            confidence=0.72,
            reasoning="Cascade analysis shows 2.5M bbl/day supply loss. Bypass capacity partially offsets but net loss drives Brent up $3-8.",
            evidence=["Hormuz flow restricted to 60%", "IRGC naval exercises ongoing"],
            created_at=now,
        ),
        PredictionOutput(
            model_id="ceasefire",
            prediction_type="ceasefire_probability",
            probability=0.62,
            direction="stable",
            magnitude_range=[0.0, 1.0],
            unit="probability",
            timeframe="14d",
            confidence=0.62,
            reasoning="Oman-mediated talks are improving dialogue but military posture remains tense.",
            evidence=["Oman mediation active", "US-Iran indirect talks confirmed"],
            created_at=now,
        ),
        PredictionOutput(
            model_id="hormuz_reopening",
            prediction_type="hormuz_reopening",
            probability=0.35,
            direction="increase",
            magnitude_range=[10.0, 40.0],
            unit="pct_reopening",
            timeframe="14d",
            confidence=0.35,
            reasoning="Partial reopening is possible if diplomacy holds, but insurers still price in meaningful disruption.",
            evidence=["Naval de-escalation signals", "Insurance premiums stabilizing"],
            created_at=now,
        ),
    ]


def _make_dry_run_markets() -> list[MarketPrice]:
    now = datetime.now(timezone.utc)
    return [
        MarketPrice(
            ticker="KXWTIMAX-26DEC31",
            source="kalshi",
            volume=12000,
            fetched_at=now,
            venue_timestamp=now,
            quote_timestamp=now,
            best_yes_bid=0.53,
            best_yes_ask=0.56,
            best_no_bid=0.44,
            best_no_ask=0.47,
            yes_bid_ask_spread=0.03,
            no_bid_ask_spread=0.03,
            yes_price=0.545,
            no_price=0.455,
            derived_price_kind="midpoint",
            data_environment="dry_run",
        ),
        MarketPrice(
            ticker="KXUSAIRANAGREEMENT-27",
            source="kalshi",
            volume=8500,
            fetched_at=now,
            venue_timestamp=now,
            quote_timestamp=now,
            best_yes_bid=0.46,
            best_yes_ask=0.49,
            best_no_bid=0.51,
            best_no_ask=0.54,
            yes_bid_ask_spread=0.03,
            no_bid_ask_spread=0.03,
            yes_price=0.475,
            no_price=0.525,
            derived_price_kind="midpoint",
            data_environment="dry_run",
        ),
        MarketPrice(
            ticker="KXCLOSEHORMUZ-27JAN",
            source="kalshi",
            volume=15000,
            fetched_at=now,
            venue_timestamp=now,
            quote_timestamp=now,
            best_yes_bid=0.58,
            best_yes_ask=0.61,
            best_no_bid=0.39,
            best_no_ask=0.42,
            yes_bid_ask_spread=0.03,
            no_bid_ask_spread=0.03,
            yes_price=0.595,
            no_price=0.405,
            derived_price_kind="midpoint",
            data_environment="dry_run",
        ),
        MarketPrice(
            ticker="KXWTIMIN-26DEC31",
            source="kalshi",
            volume=5000,
            fetched_at=now,
            venue_timestamp=now,
            quote_timestamp=now,
            best_yes_bid=0.28,
            best_yes_ask=0.31,
            best_no_bid=0.69,
            best_no_ask=0.72,
            yes_bid_ask_spread=0.03,
            no_bid_ask_spread=0.03,
            yes_price=0.295,
            no_price=0.705,
            derived_price_kind="midpoint",
            data_environment="dry_run",
        ),
    ]


def _format_market_line(market: MarketPrice) -> str:
    def _fmt(value: float | None) -> str:
        return "  N/A" if value is None else f"{value:>5.0%}"

    return (
        f"  {market.ticker:<30} {market.source:<10} "
        f"{_fmt(market.best_yes_bid)} {_fmt(market.best_yes_ask)} "
        f"{_fmt(market.best_no_bid)} {_fmt(market.best_no_ask)} "
        f"{market.derived_price_kind or 'none':<18} {market.data_environment:<8}"
    )


def _format_brief(
    predictions: list[PredictionOutput],
    market_prices: list[MarketPrice],
    divergences: list,
    budget: BudgetTracker,
    trade_table: str = "",
    signals: list | None = None,
    runtime: RuntimeConfig | None = None,
    trade_journal: list[dict] | None = None,
) -> str:
    runtime = runtime or resolve_runtime_config(dry_run=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stats = budget.stats()
    lines = [
        "=" * 72,
        "PARALLAX DAILY INTELLIGENCE BRIEF",
        f"{now} | Budget: ${stats['spend_today_usd']:.2f}/${stats['daily_cap_usd']:.2f}",
        f"Data environment: {runtime.data_environment} | Execution environment: {runtime.execution_environment}",
        "=" * 72,
        "",
        "--- PREDICTIONS ---",
        "",
    ]

    for prediction in predictions:
        title = prediction.model_id.upper().replace("_", " ")
        lines.append(title)
        lines.append(f"  Probability: {prediction.probability:.0%} | Timeframe: {prediction.timeframe}")
        lines.append(f"  Reasoning: {prediction.reasoning}")
        lines.append("")

    lines.append("--- MARKET PRICES ---")
    lines.append("")
    lines.append("  Ticker                         Venue      YBid  YAsk  NBid  NAsk  Derived Kind       Env")
    lines.append("  " + "-" * 88)
    for market in market_prices:
        lines.append(_format_market_line(market))
    lines.append("")

    lines.append("--- DIVERGENCES ---")
    lines.append("")
    lines.append("  Divergence scoring now lives in SIGNAL AUDIT with executable entry prices.")
    lines.append("")

    lines.append("--- SIGNAL AUDIT ---")
    lines.append("")
    if not signals:
        lines.append("  No signals evaluated.")
    else:
        for signal in signals:
            entry = "N/A"
            if signal.entry_price is not None:
                entry = f"{signal.entry_side or '?'} @ {signal.entry_price:.0%} ({signal.entry_price_kind})"
            derived = "N/A"
            if signal.market_derived_yes_price is not None:
                derived = f"{signal.market_derived_yes_price:.0%} ({signal.market_derived_price_kind or 'derived'})"
            lines.append(
                f"  {signal.contract_ticker:<30} {signal.model_id:<18} {signal.proxy_class:<12} {signal.signal:<8} "
                f"{(signal.effective_edge or 0.0):>+6.1%} {signal.tradeability_status:<13} exec={entry}"
            )
            lines.append(
                f"    derived_yes={derived} execution_status={signal.execution_status}"
            )
            if signal.trade_refused_reason:
                lines.append(f"    note={signal.trade_refused_reason}")
    lines.append("")

    if trade_table:
        lines.append("--- PAPER TRADES ---")
        lines.append("")
        lines.append(trade_table)
        lines.append("")

    lines.append("--- TRADE JOURNAL ---")
    lines.append("")
    if not trade_journal:
        lines.append("  No order attempts recorded.")
    else:
        for row in trade_journal:
            fill = "N/A" if row.get("avg_fill_price") is None else f"{row['avg_fill_price']:.0%}"
            pnl = ""
            if row.get("realized_pnl") is not None:
                pnl = f" pnl=${row['realized_pnl']:+.2f}"
            lines.append(
                f"  {row['ticker']:<30} {row['side']:<3} qty={row['quantity']:<3} "
                f"status={row['order_status']:<10} limit={row.get('intended_price')!s:<6} fill={fill}{pnl}"
            )
    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def _write_scheduled_output(
    run_id: str,
    predictions: list[PredictionOutput],
    signals: list,
    trade_journal: list[dict] | None = None,
    runtime: RuntimeConfig | None = None,
    divergence_count: int | None = None,
    log_dir: Path | None = None,
) -> Path:
    runtime = runtime or resolve_runtime_config(dry_run=True)
    trade_journal = trade_journal or []
    base_dir = log_dir if log_dir is not None else Path.home() / "parallax-logs"
    runs_dir = base_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_environment": runtime.data_environment,
        "execution_environment": runtime.execution_environment,
        "predictions": [prediction.model_dump() for prediction in predictions],
        "signals": [signal.model_dump(mode="json") for signal in signals],
        "trade_journal": trade_journal,
        "divergence_count": divergence_count if divergence_count is not None else len(signals),
    }
    output_path = runs_dir / f"{run_id}.json"
    output_path.write_text(json.dumps(output, indent=2, default=str))
    logger.info("Scheduled output written to %s", output_path)
    return output_path


def _persist_market_prices(
    conn: duckdb.DuckDBPyConnection,
    market_prices: list[MarketPrice],
) -> None:
    for market in market_prices:
        conn.execute(
            """
            INSERT INTO market_prices
            (ticker, source, data_environment, venue_timestamp, quote_timestamp,
             best_yes_bid, best_yes_ask, best_no_bid, best_no_ask,
             yes_bid_ask_spread, no_bid_ask_spread, yes_price, no_price,
             derived_price_kind, volume, depth_summary, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                market.ticker,
                market.source,
                market.data_environment,
                market.venue_timestamp,
                market.quote_timestamp,
                market.best_yes_bid,
                market.best_yes_ask,
                market.best_no_bid,
                market.best_no_ask,
                market.yes_bid_ask_spread,
                market.no_bid_ask_spread,
                market.yes_price,
                market.no_price,
                market.derived_price_kind,
                market.volume,
                json.dumps(
                    {
                        "yes_bid": market.yes_bid_depth.model_dump() if market.yes_bid_depth else None,
                        "yes_ask": market.yes_ask_depth.model_dump() if market.yes_ask_depth else None,
                        "no_bid": market.no_bid_depth.model_dump() if market.no_bid_depth else None,
                        "no_ask": market.no_ask_depth.model_dump() if market.no_ask_depth else None,
                    }
                ),
                market.fetched_at,
            ],
        )


OIL_CONFLICT_TICKERS = {"KXWTIMAX-26DEC31", "KXWTIMIN-26DEC31"}


def _deconflict_oil_signals(signals: list) -> None:
    """Suppress conflicting oil signals from the same model.

    If oil_price generates tradable signals on both KXWTIMAX (bullish) and
    KXWTIMIN (bearish), keep only the one with the highest effective edge.
    The loser gets downgraded to HOLD so it stays in the ledger for auditing.
    """
    oil_tradable = [
        s for s in signals
        if s.model_id == "oil_price"
        and s.contract_ticker in OIL_CONFLICT_TICKERS
        and s.signal in ("BUY_YES", "BUY_NO")
    ]
    if len(oil_tradable) <= 1:
        return

    best = max(oil_tradable, key=lambda s: abs(s.effective_edge or 0.0))
    for s in oil_tradable:
        if s.signal_id != best.signal_id:
            s.signal = "HOLD"
            s.reason = (
                f"Deconflicted: suppressed in favor of {best.contract_ticker} "
                f"(edge {best.effective_edge:.1%} vs {s.effective_edge:.1%})"
            )
            logger.info(
                "Oil deconflict: suppressed %s in favor of %s",
                s.contract_ticker, best.contract_ticker,
            )


def _load_portfolio_state(conn: duckdb.DuckDBPyConnection) -> PortfolioState:
    """Load current open positions and today's realized P&L from DuckDB."""
    rows = conn.execute("""
        SELECT ticker, side, quantity, open_quantity, entry_price, status
        FROM trade_positions
        WHERE status = 'open'
    """).fetchall()
    positions = [
        {
            "ticker": r[0], "side": r[1], "quantity": int(r[2]),
            "open_quantity": int(r[3]) if r[3] is not None else None,
            "entry_price": float(r[4]), "status": r[5],
        }
        for r in rows
    ]
    pnl_row = conn.execute("""
        SELECT COALESCE(SUM(realized_pnl), 0.0)
        FROM trade_positions
        WHERE closed_at >= CURRENT_DATE
    """).fetchone()
    daily_pnl = float(pnl_row[0]) if pnl_row else 0.0
    return PortfolioState(positions=positions, daily_realized_pnl=daily_pnl)


async def run_brief(
    dry_run: bool = False,
    no_trade: bool = False,
    scheduled: bool = False,
    log_dir: Path | None = None,
) -> str:
    budget = BudgetTracker(daily_cap_usd=20.0)
    run_id = str(uuid.uuid4())
    runtime = resolve_runtime_config(dry_run=dry_run)
    conn = duckdb.connect(runtime.db_path)
    create_tables(conn)
    _persist_run_start(conn, run_id, runtime)
    logger.info(
        "Running brief (run_id=%s data_environment=%s execution_environment=%s db=%s)",
        run_id,
        runtime.data_environment,
        runtime.execution_environment,
        runtime.db_path,
    )

    events: list[dict] = []
    if dry_run:
        predictions = _make_dry_run_predictions()
        market_prices = _make_dry_run_markets()
    else:
        anthropic_client = _init_anthropic()
        config = _load_config()
        cascade = CascadeEngine(config=config)
        world_state = WorldState()
        # Initialize Hormuz with current blockade conditions
        # ~2M bbl/day trickle flow (10% of 20M pre-war capacity)
        # Based on crisis context: "8 ships in 2 days vs 100+/day pre-war"
        world_state.update_cell(
            cell_id=1,
            influence="iran",
            threat_level=0.9,
            flow=2_000_000,
            status="blocked",
        )
        events, prices, kalshi_markets, poly_markets = await asyncio.gather(
            _fetch_gdelt_events(),
            _fetch_oil_prices(),
            _fetch_kalshi_markets(),
            _fetch_polymarket_markets(),
        )
        market_prices = kalshi_markets + poly_markets
        oil_pred = OilPricePredictor(cascade, budget, anthropic_client)
        ceasefire_pred = CeasefirePredictor(budget, anthropic_client)
        hormuz_pred = HormuzReopeningPredictor(cascade, budget, anthropic_client)
        predictions = list(
            await asyncio.gather(
                oil_pred.predict(events, prices, world_state, db_conn=conn),
                ceasefire_pred.predict(events, db_conn=conn),
                hormuz_pred.predict(events, world_state, db_conn=conn),
            ),
        )

    _persist_market_prices(conn, market_prices)
    registry = ContractRegistry(conn)
    registry.seed_initial_contracts()
    policy = MappingPolicy(registry=registry, min_effective_edge_pct=5.0)
    pred_logger = PredictionLogger(conn)
    ledger = SignalLedger(conn)

    for prediction in predictions:
        news_context = [] if dry_run else [
            {
                "title": event["title"],
                "url": event["url"],
                "source": event["source"],
                "fetched_at": event.get("published_at", ""),
            }
            for event in events[:20]
        ]
        pred_logger.log_prediction(
            run_id,
            prediction,
            news_context,
            None,
            data_environment=runtime.data_environment,
        )

    raw_probs: dict[str, float] = {}
    for prediction in predictions:
        calibrated, raw = recalibrate_probability(prediction.probability, prediction.model_id, conn)
        raw_probs[prediction.model_id] = raw
        prediction.probability = calibrated

    policy.update_thresholds_from_history(conn)
    policy.update_discounts_from_history(conn)

    all_signals = []
    active_contracts = {contract.ticker: contract for contract in registry.get_active_contracts()}
    for prediction in predictions:
        mappings = policy.evaluate(prediction, market_prices)
        for mapping in mappings:
            market = next((m for m in market_prices if m.ticker == mapping.contract_ticker), None)
            if market is None:
                continue
            signal = ledger.record_signal(
                prediction,
                mapping,
                market,
                contract_title=active_contracts.get(mapping.contract_ticker).title if mapping.contract_ticker in active_contracts else None,
                run_id=run_id,
                raw_probability=raw_probs.get(prediction.model_id),
                data_environment=runtime.data_environment,
                execution_environment=runtime.execution_environment,
            )
            all_signals.append(signal)

    # Deconflict oil contracts: don't let one oil_price prediction generate
    # tradable signals on both KXWTIMAX (bullish) and KXWTIMIN (bearish).
    # Keep only the signal with the highest effective edge.
    _deconflict_oil_signals(all_signals)

    trade_journal: list[dict] = []
    if not dry_run and not no_trade:
        kalshi_key = os.environ.get("KALSHI_API_KEY", "")
        kalshi_pk = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
        if kalshi_key and kalshi_pk:
            kalshi = KalshiClient(api_key=kalshi_key, private_key_path=kalshi_pk)
            tracker = PaperTradeTracker(conn=conn, ledger=ledger, kalshi_client=kalshi)
            risk_limits = load_risk_limits()
            allocator = PortfolioAllocator(risk_limits)
            portfolio_state = _load_portfolio_state(conn)
            for signal in ledger.get_actionable_signals():
                if signal.entry_price is None or signal.entry_side is None:
                    continue
                proposed = ProposedTrade(
                    ticker=signal.contract_ticker,
                    side=signal.entry_side,
                    price=signal.entry_price,
                    theme=signal.model_id or "general",
                    signal_id=signal.signal_id,
                )
                auth = allocator.authorize_trade(proposed, portfolio_state)
                if not auth.authorized:
                    logger.info(
                        "Allocator blocked %s: %s", signal.contract_ticker, auth.block_reason,
                    )
                    continue
                await tracker.execute_signal(signal, quantity=auth.allowed_size)
            trade_journal = tracker.get_trade_journal()
    else:
        trade_journal = []

    refreshed_signals = ledger.get_signals(limit=200)
    brief = _format_brief(
        predictions,
        market_prices,
        [],
        budget,
        signals=refreshed_signals,
        runtime=runtime,
        trade_journal=trade_journal,
    )
    print(brief)

    if scheduled:
        _write_scheduled_output(
            run_id,
            predictions,
            refreshed_signals,
            runtime=runtime,
            trade_journal=trade_journal,
            divergence_count=len(refreshed_signals),
            log_dir=log_dir,
        )

    _persist_run_end(
        conn,
        run_id,
        status="completed",
        predictions_count=len(predictions),
        signals_count=len(all_signals),
        trades_count=len(trade_journal),
    )
    conn.close()
    return brief


async def _run_check_resolutions() -> None:
    from parallax.scoring.resolution import check_resolutions

    runtime = resolve_runtime_config(dry_run=False)
    conn = duckdb.connect(runtime.db_path)
    create_tables(conn)
    api_key = os.environ.get("KALSHI_API_KEY", "")
    pk_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if not api_key or not pk_path:
        print("ERROR: KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH required for resolution checking")
        conn.close()
        return

    client = KalshiClient(
        api_key=api_key,
        private_key_path=pk_path,
        base_url="https://api.elections.kalshi.com/trade-api/v2",
    )
    results = await check_resolutions(conn, client)
    if results:
        print(f"Resolved {len(results)} contract(s):")
        for result in results:
            print(
                f"  {result['ticker']}: settlement={result['resolution_price']} "
                f"signals={result['signals_updated']} positions={result['positions_closed']}"
            )
    else:
        print("No contracts have settled since last check.")
    conn.close()


def _run_calibration() -> None:
    from parallax.scoring.calibration import calibration_report

    runtime = resolve_runtime_config(dry_run=False)
    conn = duckdb.connect(runtime.db_path)
    create_tables(conn)
    print(calibration_report(conn))
    conn.close()


def _run_report_card() -> None:
    from parallax.scoring.report_card import generate_report_card

    runtime = resolve_runtime_config(dry_run=False)
    conn = duckdb.connect(runtime.db_path)
    create_tables(conn)
    print(generate_report_card(conn))
    conn.close()


def _run_scorecard(date_str: str | None = None) -> None:
    from parallax.scoring.scorecard import compute_daily_scorecard

    runtime = resolve_runtime_config(dry_run=False)
    conn = duckdb.connect(runtime.db_path)
    create_tables(conn)
    print(compute_daily_scorecard(conn, date_str))
    conn.close()


def _init_anthropic():
    import anthropic

    return anthropic.AsyncAnthropic()


def _load_config() -> ScenarioConfig:
    if SCENARIO_CONFIG_PATH.exists():
        return load_scenario_config(SCENARIO_CONFIG_PATH)
    alt = Path("backend/config/scenario_hormuz.yaml")
    if alt.exists():
        return load_scenario_config(alt)
    raise FileNotFoundError(f"Scenario config not found at {SCENARIO_CONFIG_PATH} or {alt}")


async def _fetch_gdelt_events() -> list[dict]:
    from parallax.ingestion.gdelt_doc import fetch_gdelt_docs
    from parallax.ingestion.google_news import fetch_google_news
    from parallax.ingestion.truth_social import fetch_truth_social

    events = []
    seen: set[str] = set()
    try:
        google_news, gdelt_events, truth_events = await asyncio.gather(
            fetch_google_news(seen_hashes=seen),
            fetch_gdelt_docs(timespan="24h", seen_hashes=seen),
            fetch_truth_social(seen_hashes=seen),
            return_exceptions=True,
        )
        if isinstance(google_news, list):
            events.extend(google_news)
            seen.update(event.event_hash for event in google_news)
        if isinstance(gdelt_events, list):
            for event in gdelt_events:
                if event.event_hash not in seen:
                    events.append(event)
                    seen.add(event.event_hash)
        if isinstance(truth_events, list):
            for event in truth_events:
                if event.event_hash not in seen:
                    events.append(event)
                    seen.add(event.event_hash)
    except Exception:
        logger.exception("Failed to fetch news events")

    return [
        {
            "title": event.title,
            "url": event.url,
            "source": event.source,
            "published_at": event.published_at.isoformat(),
            "snippet": event.snippet,
            "query": event.query,
        }
        for event in events
    ]


async def _fetch_oil_prices() -> list[dict]:
    api_key = os.environ.get("EIA_API_KEY", "")
    if not api_key:
        logger.warning("EIA_API_KEY not set, skipping oil price fetch")
        return []
    try:
        from parallax.ingestion.oil_prices import fetch_brent

        return await fetch_brent(api_key)
    except Exception:
        logger.exception("Failed to fetch oil prices")
        return []


async def _fetch_kalshi_markets() -> list[MarketPrice]:
    api_key = os.environ.get("KALSHI_API_KEY", "")
    pk_path = os.environ.get("KALSHI_PRIVATE_KEY_PATH", "")
    if not api_key or not pk_path:
        logger.warning("Kalshi credentials not set, skipping market fetch")
        return []
    try:
        client = KalshiClient(
            api_key=api_key,
            private_key_path=pk_path,
            base_url="https://api.elections.kalshi.com/trade-api/v2",
        )
        prices: list[MarketPrice] = []
        for event_ticker in IRAN_EVENT_TICKERS:
            try:
                data = await client._request(
                    "GET",
                    "/markets",
                    params={"event_ticker": event_ticker, "limit": 10},
                )
                for market in data.get("markets", []):
                    if market.get("status") not in ("open", "active"):
                        continue
                    ticker = market.get("ticker", "")
                    if ticker and not any(existing.ticker == ticker for existing in prices):
                        normalized = await client.get_market_price(ticker)
                        if normalized.best_yes_ask is not None or normalized.best_no_ask is not None:
                            prices.append(normalized)
            except Exception:
                logger.debug("Failed to fetch Kalshi event %s", event_ticker, exc_info=True)
        return prices
    except Exception:
        logger.exception("Failed to fetch Kalshi markets")
        return []


async def _fetch_polymarket_markets() -> list[MarketPrice]:
    try:
        client = PolymarketClient()
        return await client.get_iran_markets()
    except Exception:
        logger.exception("Failed to fetch Polymarket markets")
        return []


def main():
    parser = argparse.ArgumentParser(description="Parallax Daily Intelligence Brief")
    parser.add_argument("--dry-run", action="store_true", help="Use mock predictions and isolated dry-run storage")
    parser.add_argument("--no-trade", action="store_true", help="Do not place paper orders")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--check-resolutions", action="store_true", help="Backfill settled contracts")
    parser.add_argument("--calibration", action="store_true", help="Print signal-quality report")
    parser.add_argument("--scheduled", action="store_true", help="Write structured JSON output")
    parser.add_argument("--report-card", action="store_true", help="Print trading report card")
    parser.add_argument("--scorecard", action="store_true", help="Compute daily scorecard metrics")
    parser.add_argument("--date", type=str, default=None, help="Date for scorecard (YYYY-MM-DD, default today)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.check_resolutions:
        asyncio.run(_run_check_resolutions())
        return
    if args.calibration:
        _run_calibration()
        return
    if args.report_card:
        _run_report_card()
        return
    if args.scorecard:
        _run_scorecard(args.date)
        return

    asyncio.run(run_brief(dry_run=args.dry_run, no_trade=args.no_trade, scheduled=args.scheduled))


if __name__ == "__main__":
    main()
