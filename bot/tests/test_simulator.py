"""
Tests for TradeSimulator — open/close, SL/TP, fee model, stats
"""
import pytest
from datetime import datetime
from execution.simulator import TradeSimulator, SimulatedPosition


@pytest.fixture
def sim():
    return TradeSimulator(starting_balance=10.0, max_positions=3)


# ────────────────────────── open position ──────────────────────────

class TestOpenPosition:
    def test_open_deducts_balance(self, sim):
        sim.open_position("A", "TEST", current_price=0.01, amount_sol=1.0)
        assert sim.stats.current_balance == pytest.approx(9.0)

    def test_open_respects_max_positions(self, sim):
        sim.open_position("A", "A", 0.01, 1.0)
        sim.open_position("B", "B", 0.01, 1.0)
        sim.open_position("C", "C", 0.01, 1.0)
        result = sim.open_position("D", "D", 0.01, 1.0)
        assert result is None

    def test_open_rejects_duplicate(self, sim):
        sim.open_position("A", "A", 0.01, 1.0)
        result = sim.open_position("A", "A", 0.02, 1.0)
        assert result is None

    def test_open_rejects_insufficient_balance(self, sim):
        result = sim.open_position("A", "A", 0.01, 100.0)
        assert result is None

    def test_open_applies_slippage(self, sim):
        """Entry price should be >= current price (slippage is adverse)."""
        pos = sim.open_position("A", "A", current_price=1.0, amount_sol=1.0)
        assert pos.entry_price >= 1.0

    def test_open_deducts_fees(self, sim):
        """Token amount should reflect fees + slippage."""
        pos = sim.open_position("A", "A", current_price=1.0, amount_sol=1.0)
        # effective_amount = 1.0 * (1 - 0.75%) = 0.9925 SOL
        # Then entry_price >= 1.0 due to slippage
        # So token_amount < 1.0
        assert pos.token_amount < 1.0


# ────────────────────────── close position ──────────────────────────

class TestClosePosition:
    def test_close_credits_balance(self, sim):
        sim.open_position("A", "A", 1.0, 2.0)
        # balance is now 8.0
        sim.close_position("A", current_price=1.0, reason="manual")
        # Should have roughly 2 SOL back (minus fees/slippage both ways)
        assert sim.stats.current_balance > 9.0  # less than 10 due to round-trip fees

    def test_close_nonexistent_returns_none(self, sim):
        assert sim.close_position("X", 1.0) is None

    def test_close_records_stats(self, sim):
        sim.open_position("A", "A", 1.0, 1.0)
        sim.close_position("A", 1.5, "tp")
        assert sim.stats.total_trades == 1
        assert sim.stats.winning_trades == 1

    def test_close_loss_records_loss(self, sim):
        sim.open_position("A", "A", 1.0, 1.0)
        sim.close_position("A", 0.5, "sl")
        assert sim.stats.losing_trades == 1


# ────────────────────────── SL/TP logic ──────────────────────────

class TestSimulatedSLTP:
    def test_stop_loss_detection(self):
        pos = SimulatedPosition(
            token_address="A", token_symbol="A",
            entry_price=1.0, entry_time=datetime.now(),
            amount_sol=1.0, token_amount=1.0,
            stop_loss=15.0, take_profit=50.0,
            current_price=1.0
        )
        pos.update_price(0.84)  # -16%
        assert pos.should_stop_loss() is True
        assert pos.should_take_profit() is False

    def test_take_profit_detection(self):
        pos = SimulatedPosition(
            token_address="A", token_symbol="A",
            entry_price=1.0, entry_time=datetime.now(),
            amount_sol=1.0, token_amount=1.0,
            stop_loss=15.0, take_profit=50.0,
            current_price=1.0
        )
        pos.update_price(1.55)  # +55%
        assert pos.should_take_profit() is True
        assert pos.should_stop_loss() is False

    def test_no_trigger_in_range(self):
        pos = SimulatedPosition(
            token_address="A", token_symbol="A",
            entry_price=1.0, entry_time=datetime.now(),
            amount_sol=1.0, token_amount=1.0,
            stop_loss=15.0, take_profit=50.0,
            current_price=1.0
        )
        pos.update_price(1.10)  # +10%
        assert pos.should_stop_loss() is False
        assert pos.should_take_profit() is False


# ────────────────────────── update_positions batch ──────────────────────────

class TestUpdatePositions:
    def test_sl_triggers_auto_close(self, sim):
        sim.open_position("A", "A", 1.0, 1.0, stop_loss=15.0, take_profit=50.0)
        triggered = sim.update_positions({"A": 0.80})  # -20%
        assert len(triggered) == 1
        assert triggered[0].exit_reason == "stop_loss"
        assert "A" not in sim.positions

    def test_tp_triggers_auto_close(self, sim):
        sim.open_position("A", "A", 1.0, 1.0, stop_loss=15.0, take_profit=50.0)
        triggered = sim.update_positions({"A": 1.60})  # +60%
        assert len(triggered) == 1
        assert triggered[0].exit_reason == "take_profit"

    def test_no_trigger_keeps_open(self, sim):
        sim.open_position("A", "A", 1.0, 1.0, stop_loss=15.0, take_profit=50.0)
        triggered = sim.update_positions({"A": 1.10})
        assert len(triggered) == 0
        assert "A" in sim.positions


# ────────────────────────── stats / ROI ──────────────────────────

class TestStats:
    def test_roi_calculation(self, sim):
        assert sim.stats.roi == pytest.approx(0.0)
        sim.stats.current_balance = 12.0
        assert sim.stats.roi == pytest.approx(20.0)  # (12-10)/10 * 100

    def test_win_rate(self, sim):
        sim.stats.total_trades = 10
        sim.stats.winning_trades = 6
        assert sim.stats.win_rate == pytest.approx(60.0)

    def test_win_rate_zero_trades(self, sim):
        assert sim.stats.win_rate == 0.0
