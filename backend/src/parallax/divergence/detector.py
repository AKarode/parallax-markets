"""Divergence detector: compares model predictions against market prices.

Flags divergences where the model's probability estimate differs
significantly from the market-implied probability, generating
BUY_YES / BUY_NO / HOLD signals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel

from parallax.markets.schemas import MarketPrice
from parallax.prediction.schemas import PredictionOutput

logger = logging.getLogger(__name__)


class Divergence(BaseModel):
    """A detected divergence between model prediction and market price."""

    model_id: str
    prediction: PredictionOutput
    market_price: MarketPrice
    model_probability: float
    market_probability: float
    edge: float  # model_prob - market_prob (positive = model thinks underpriced)
    edge_pct: float  # edge as percentage
    signal: str  # "BUY_YES", "BUY_NO", "HOLD"
    strength: str  # "strong" (>15%), "moderate" (10-15%), "weak" (5-10%)
    created_at: datetime


class DivergenceDetector:
    """Compare model predictions against market prices and flag divergences."""

    def __init__(self, min_edge_pct: float = 5.0) -> None:
        self._min_edge = min_edge_pct / 100.0

    def detect(
        self,
        predictions: list[PredictionOutput],
        market_prices: list[MarketPrice],
    ) -> list[Divergence]:
        """Compare model predictions against market prices.

        Matching logic: Match predictions to markets by kalshi_ticker
        or polymarket_id. A prediction gets matched to the corresponding
        MarketPrice by ticker.

        Signal logic:
        - If model_prob > market_prob + min_edge: BUY_YES
        - If model_prob < market_prob - min_edge: BUY_NO
        - Otherwise: HOLD

        Strength:
        - |edge| > 0.15: "strong"
        - |edge| > 0.10: "moderate"
        - |edge| > 0.05: "weak"
        """
        # Build lookup: ticker -> MarketPrice
        market_by_ticker: dict[str, MarketPrice] = {}
        for mp in market_prices:
            market_by_ticker[mp.ticker] = mp

        divergences: list[Divergence] = []

        for pred in predictions:
            matched_market = self._match_prediction(pred, market_by_ticker)
            if matched_market is None:
                continue

            model_prob = pred.probability
            market_prob = matched_market.yes_price
            edge = model_prob - market_prob
            abs_edge = abs(edge)

            # Determine signal
            if edge > self._min_edge:
                signal = "BUY_YES"
            elif edge < -self._min_edge:
                signal = "BUY_NO"
            else:
                signal = "HOLD"

            # Determine strength
            if abs_edge > 0.15:
                strength = "strong"
            elif abs_edge > 0.10:
                strength = "moderate"
            elif abs_edge > 0.05:
                strength = "weak"
            else:
                strength = "negligible"

            divergences.append(Divergence(
                model_id=pred.model_id,
                prediction=pred,
                market_price=matched_market,
                model_probability=model_prob,
                market_probability=market_prob,
                edge=edge,
                edge_pct=edge * 100,
                signal=signal,
                strength=strength,
                created_at=datetime.now(timezone.utc),
            ))

        return divergences

    @staticmethod
    def _match_prediction(
        pred: PredictionOutput,
        market_by_ticker: dict[str, MarketPrice],
    ) -> MarketPrice | None:
        """Find matching market for a prediction."""
        # Try kalshi_ticker first
        if pred.kalshi_ticker and pred.kalshi_ticker in market_by_ticker:
            return market_by_ticker[pred.kalshi_ticker]
        # Try polymarket_id
        if pred.polymarket_id and pred.polymarket_id in market_by_ticker:
            return market_by_ticker[pred.polymarket_id]
        # Try matching by prediction_type in ticker
        for ticker, mp in market_by_ticker.items():
            if pred.prediction_type.lower() in ticker.lower():
                return mp
        return None
