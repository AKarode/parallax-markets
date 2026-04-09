"""Portfolio allocator enforcing configuration-backed risk limits."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from parallax.config.risk import RiskLimits
from parallax.portfolio.schemas import (
    CurrentPosition,
    PortfolioState,
    ProposedTrade,
    TradeAuthorization,
    dump_model,
)


class PortfolioAllocator:
    """Authorize and size candidate trades against hard risk caps."""

    def __init__(self, risk_limits: RiskLimits) -> None:
        self._risk_limits = risk_limits

    @property
    def risk_limits(self) -> RiskLimits:
        return self._risk_limits

    def authorize_trade(
        self,
        proposed_trade: ProposedTrade | Mapping[str, Any] | BaseModel,
        current_positions: PortfolioState | Sequence[CurrentPosition] | Mapping[str, Any] | BaseModel,
    ) -> TradeAuthorization:
        trade = self._coerce_trade(proposed_trade)
        portfolio_state = self._coerce_portfolio_state(current_positions)

        requested_size = trade.normalized_size(self._risk_limits.default_order_size)
        if requested_size < self._risk_limits.min_order_size:
            return TradeAuthorization(
                authorized=False,
                allowed_size=0,
                block_reason=(
                    "Requested size below minimum order size "
                    f"({self._risk_limits.min_order_size})"
                ),
            )

        if portfolio_state.open_order_count() >= self._risk_limits.max_open_orders:
            return TradeAuthorization(
                authorized=False,
                allowed_size=0,
                block_reason="Max open orders reached",
            )

        if (
            not portfolio_state.has_open_position(trade.ticker, trade.side)
            and portfolio_state.open_position_count() >= self._risk_limits.max_open_positions
        ):
            return TradeAuthorization(
                authorized=False,
                allowed_size=0,
                block_reason="Max open positions reached",
            )

        remaining_daily_loss = self._remaining_daily_loss_capacity(portfolio_state)
        if remaining_daily_loss <= 0.0:
            return TradeAuthorization(
                authorized=False,
                allowed_size=0,
                block_reason="Daily loss limit reached",
            )

        allowed_size = requested_size
        limiting_reason = ""

        for candidate_size, reason in self._candidate_size_limits(trade, portfolio_state, remaining_daily_loss):
            if candidate_size < allowed_size:
                allowed_size = candidate_size
                limiting_reason = reason

        if allowed_size < self._risk_limits.min_order_size:
            return TradeAuthorization(
                authorized=False,
                allowed_size=0,
                block_reason=limiting_reason or "Insufficient capacity for minimum order size",
            )

        if allowed_size < requested_size:
            return TradeAuthorization(
                authorized=True,
                allowed_size=allowed_size,
                block_reason=limiting_reason,
            )

        return TradeAuthorization(
            authorized=True,
            allowed_size=allowed_size,
            block_reason="",
        )

    def _candidate_size_limits(
        self,
        trade: ProposedTrade,
        portfolio_state: PortfolioState,
        remaining_daily_loss: float,
    ) -> list[tuple[int, str]]:
        loss_per_contract = trade.max_loss_per_contract()
        limits: list[tuple[int, str]] = []

        remaining_notional = self._risk_limits.max_notional - portfolio_state.gross_notional()
        limits.append(
            (
                self._contracts_affordable(remaining_notional, loss_per_contract),
                "Max notional reached",
            ),
        )

        theme_limit = self._risk_limits.theme_limit_for(trade.theme)
        if theme_limit is not None:
            remaining_theme_capacity = theme_limit - portfolio_state.theme_notional(trade.theme)
            limits.append(
                (
                    self._contracts_affordable(remaining_theme_capacity, loss_per_contract),
                    f"Theme exposure limit reached for {trade.theme}",
                ),
            )

        limits.append(
            (
                self._contracts_affordable(remaining_daily_loss, loss_per_contract),
                "Daily loss limit reached",
            ),
        )
        return limits

    @staticmethod
    def _contracts_affordable(capacity: float, loss_per_contract: float) -> int:
        if capacity <= 0.0:
            return 0
        return max(0, math.floor(capacity / loss_per_contract))

    def _remaining_daily_loss_capacity(self, portfolio_state: PortfolioState) -> float:
        return _remaining_daily_loss_capacity(
            self._risk_limits.daily_loss_limit,
            portfolio_state.daily_realized_pnl,
        )

    def _coerce_trade(
        self,
        proposed_trade: ProposedTrade | Mapping[str, Any] | BaseModel,
    ) -> ProposedTrade:
        if isinstance(proposed_trade, ProposedTrade):
            return proposed_trade
        return ProposedTrade.model_validate(dump_model(proposed_trade))

    def _coerce_portfolio_state(
        self,
        current_positions: PortfolioState | Sequence[CurrentPosition] | Mapping[str, Any] | BaseModel,
    ) -> PortfolioState:
        if isinstance(current_positions, PortfolioState):
            return current_positions

        payload = dump_model(current_positions)
        if isinstance(payload, Mapping):
            return PortfolioState.model_validate(payload)

        if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
            return PortfolioState(positions=[dump_model(item) for item in payload])

        raise TypeError(
            "current_positions must be a PortfolioState, mapping, or sequence of positions",
        )


def _remaining_daily_loss_capacity(
    daily_loss_limit: float,
    realized_pnl: float,
) -> float:
    consumed_loss = max(0.0, -realized_pnl)
    return max(0.0, daily_loss_limit - consumed_loss)
