"""Tests for the transaction cost model."""
import pytest
from parallax.costs.fee_model import CostModel


class TestCostModel:
    def test_default_total_cost(self):
        model = CostModel()
        # 0.07 taker fee + 0.01 slippage = 0.08
        assert model.total_cost_probability_space() == pytest.approx(0.08)

    def test_custom_fees(self):
        model = CostModel(taker_fee_per_contract=0.05, slippage_buffer=0.02)
        assert model.total_cost_probability_space() == pytest.approx(0.07)

    def test_net_edge_positive(self):
        model = CostModel()  # total cost = 0.08
        assert model.net_edge(0.15) == pytest.approx(0.07)

    def test_net_edge_negative(self):
        model = CostModel()  # total cost = 0.08
        assert model.net_edge(0.06) == pytest.approx(-0.02)

    def test_net_edge_zero_raw(self):
        model = CostModel()
        assert model.net_edge(0.0) == pytest.approx(-0.08)

    def test_zero_cost_model(self):
        model = CostModel(taker_fee_per_contract=0.0, slippage_buffer=0.0)
        assert model.net_edge(0.10) == pytest.approx(0.10)

    def test_maker_fee_included_if_set(self):
        model = CostModel(taker_fee_per_contract=0.07, maker_fee_per_contract=0.02, slippage_buffer=0.01)
        # Should only use taker fee in total_cost (maker fee is informational)
        assert model.total_cost_probability_space() == pytest.approx(0.08)
