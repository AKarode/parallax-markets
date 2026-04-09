"""Divergence detector using executable entry prices rather than snapshots."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel

from parallax.costs.fee_model import CostModel
from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput

logger = logging.getLogger(__name__)


class Divergence(BaseModel):
    """A detected divergence between model prediction and a specific entry path."""

    model_id: str
    prediction: PredictionOutput
    market_price: MarketPrice
    model_probability: float
    market_probability: float | None
    buy_yes_edge: float | None
    buy_no_edge: float | None
    edge: float
    gross_edge: float = 0.0
    net_edge: float = 0.0
    edge_pct: float
    signal: str
    strength: str
    entry_side: str | None
    entry_price: float | None
    entry_price_kind: str | None
    entry_price_is_executable: bool
    tradeability_status: str
    created_at: datetime


class DivergenceDetector:
    """Compare model predictions against executable quotes and flag trades."""

    def __init__(self, min_edge_pct: float = 5.0, cost_model: CostModel | None = None) -> None:
        self._min_edge = min_edge_pct / 100.0
        self._cost_model = cost_model

    def detect(
        self,
        predictions: list[PredictionOutput],
        market_prices: list[MarketPrice],
    ) -> list[Divergence]:
        market_by_ticker = {market.ticker: market for market in market_prices}
        divergences: list[Divergence] = []

        for prediction in predictions:
            matched_market = self._match_prediction(prediction, market_by_ticker)
            if matched_market is None:
                continue

            model_yes_probability = prediction.probability
            model_no_probability = 1.0 - model_yes_probability
            buy_yes_edge = None
            buy_no_edge = None

            if matched_market.best_yes_ask is not None:
                buy_yes_edge = model_yes_probability - matched_market.best_yes_ask
            if matched_market.best_no_ask is not None:
                buy_no_edge = model_no_probability - matched_market.best_no_ask

            signal = "HOLD"
            edge = 0.0
            entry_side = None
            entry_price = None
            entry_price_kind = None
            entry_price_is_executable = False
            tradeability_status = "tradable"

            candidates: list[tuple[str, float, float]] = []
            if buy_yes_edge is not None:
                candidates.append(("yes", buy_yes_edge, matched_market.best_yes_ask or 0.0))
            if buy_no_edge is not None:
                candidates.append(("no", buy_no_edge, matched_market.best_no_ask or 0.0))

            gross_edge_value = 0.0
            net_edge_value = 0.0

            if not candidates:
                tradeability_status = "non_tradable"
                signal = "REFUSED"
            else:
                best_side, best_edge, best_price = max(candidates, key=lambda item: item[1])
                gross_edge_value = best_edge
                if self._cost_model is not None:
                    net_edge_value = self._cost_model.net_edge(best_edge)
                else:
                    net_edge_value = best_edge

                if net_edge_value >= self._min_edge:
                    entry_side = best_side
                    entry_price = best_price
                    entry_price_is_executable = True
                    entry_price_kind = (
                        "best_yes_ask" if best_side == "yes" else "best_no_ask"
                    )
                    signal = "BUY_YES" if best_side == "yes" else "BUY_NO"

                sign = 1.0 if best_side == "yes" else -1.0
                edge = sign * net_edge_value

            divergences.append(
                Divergence(
                    model_id=prediction.model_id,
                    prediction=prediction,
                    market_price=matched_market,
                    model_probability=model_yes_probability,
                    market_probability=matched_market.reference_price(),
                    buy_yes_edge=buy_yes_edge,
                    buy_no_edge=buy_no_edge,
                    edge=edge,
                    gross_edge=sign * gross_edge_value if candidates else 0.0,
                    net_edge=sign * net_edge_value if candidates else 0.0,
                    edge_pct=edge * 100,
                    signal=signal,
                    strength=self._strength(abs(edge)),
                    entry_side=entry_side,
                    entry_price=entry_price,
                    entry_price_kind=entry_price_kind,
                    entry_price_is_executable=entry_price_is_executable,
                    tradeability_status=tradeability_status,
                    created_at=datetime.now(timezone.utc),
                ),
            )

        return divergences

    @staticmethod
    def _strength(abs_edge: float) -> str:
        if abs_edge > 0.15:
            return "strong"
        if abs_edge > 0.10:
            return "moderate"
        if abs_edge > 0.05:
            return "weak"
        return "negligible"

    @staticmethod
    def _match_prediction(
        pred: PredictionOutput,
        market_by_ticker: dict[str, MarketPrice],
    ) -> MarketPrice | None:
        if pred.kalshi_ticker and pred.kalshi_ticker in market_by_ticker:
            return market_by_ticker[pred.kalshi_ticker]
        if pred.polymarket_id and pred.polymarket_id in market_by_ticker:
            return market_by_ticker[pred.polymarket_id]
        for ticker, market in market_by_ticker.items():
            if pred.prediction_type.lower() in ticker.lower():
                return market
        return None
