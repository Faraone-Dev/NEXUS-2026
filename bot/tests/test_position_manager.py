"""
Tests for PositionManager — SL/TP logic, persistence, limits
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Patch config before importing PositionManager so module-level import works
_mock_config = MagicMock()
_mock_config.STOP_LOSS_PERCENT = 15.0
_mock_config.TAKE_PROFIT_PERCENT = 50.0
_mock_config.MAX_POSITIONS = 5

with patch.dict("sys.modules", {}):
    pass

import sys
# Pre-patch config in the module namespace
import execution.position_manager as pm_mod
_original_config = pm_mod.config
pm_mod.config = _mock_config

from execution.position_manager import PositionManager, Position


@pytest.fixture
def pm(tmp_path):
    """PositionManager with temp storage and mocked config."""
    pm_mod.config = _mock_config
    _mock_config.STOP_LOSS_PERCENT = 15.0
    _mock_config.TAKE_PROFIT_PERCENT = 50.0
    _mock_config.MAX_POSITIONS = 5
    return PositionManager(data_dir=str(tmp_path))


# ────────────────────────── open / close ──────────────────────────

class TestOpenClose:
    def test_open_position(self, pm):
        pos = pm.open_position(
            token_mint="AAAA1111", token_symbol="TEST",
            entry_price=0.001, amount=1000, sol_invested=0.1
        )
        assert pos.token_mint == "AAAA1111"
        assert pos.entry_price == 0.001
        assert pm.get_position_count() == 1

    def test_close_position(self, pm):
        pos = pm.open_position(
            token_mint="AAAA1111", token_symbol="TEST",
            entry_price=0.001, amount=1000, sol_invested=0.1
        )
        closed = pm.close_position(pos.id)
        assert closed is not None
        assert pm.get_position_count() == 0

    def test_close_nonexistent_returns_none(self, pm):
        assert pm.close_position("nonexistent") is None

    def test_find_by_token(self, pm):
        pm.open_position(
            token_mint="AAAA1111", token_symbol="TEST",
            entry_price=0.001, amount=1000, sol_invested=0.1
        )
        assert pm.get_position_by_token("AAAA1111") is not None
        assert pm.get_position_by_token("BBBB2222") is None


# ────────────────────────── PnL calculation ──────────────────────────

class TestPnL:
    def test_pnl_positive(self, pm):
        pos = pm.open_position(
            token_mint="AAAA1111", token_symbol="TEST",
            entry_price=1.0, amount=100, sol_invested=1.0
        )
        pm.update_price(pos.id, 1.5)
        updated = pm.get_position(pos.id)
        assert updated.pnl_percent == pytest.approx(50.0)

    def test_pnl_negative(self, pm):
        pos = pm.open_position(
            token_mint="AAAA1111", token_symbol="TEST",
            entry_price=1.0, amount=100, sol_invested=1.0
        )
        pm.update_price(pos.id, 0.8)
        updated = pm.get_position(pos.id)
        assert updated.pnl_percent == pytest.approx(-20.0)

    def test_pnl_zero_entry_price(self, pm):
        """Position with entry_price=0 should return 0 PnL (guard in property)."""
        pos = pm.open_position(
            token_mint="AAAA1111", token_symbol="TEST",
            entry_price=0, amount=100, sol_invested=0.1
        )
        assert pos.pnl_percent == 0


# ────────────────────────── SL/TP triggers ──────────────────────────

class TestTriggers:
    def test_stop_loss_triggers(self, pm):
        _mock_config.STOP_LOSS_PERCENT = 15.0
        _mock_config.TAKE_PROFIT_PERCENT = 50.0

        pos = pm.open_position(
            token_mint="AAAA1111", token_symbol="TEST",
            entry_price=1.0, amount=100, sol_invested=1.0
        )
        # Drop 16% — should trigger SL at -15%
        pm.update_price(pos.id, 0.84)
        sl, tp = pm.check_triggers()
        assert len(sl) == 1
        assert len(tp) == 0

    def test_take_profit_triggers(self, pm):
        _mock_config.STOP_LOSS_PERCENT = 15.0
        _mock_config.TAKE_PROFIT_PERCENT = 50.0

        pos = pm.open_position(
            token_mint="AAAA1111", token_symbol="TEST",
            entry_price=1.0, amount=100, sol_invested=1.0
        )
        # Rise 55% — should trigger TP at +50%
        pm.update_price(pos.id, 1.55)
        sl, tp = pm.check_triggers()
        assert len(sl) == 0
        assert len(tp) == 1

    def test_no_trigger_in_range(self, pm):
        _mock_config.STOP_LOSS_PERCENT = 15.0
        _mock_config.TAKE_PROFIT_PERCENT = 50.0

        pos = pm.open_position(
            token_mint="AAAA1111", token_symbol="TEST",
            entry_price=1.0, amount=100, sol_invested=1.0
        )
        pm.update_price(pos.id, 1.10)
        sl, tp = pm.check_triggers()
        assert len(sl) == 0
        assert len(tp) == 0


# ────────────────────────── max positions ──────────────────────────

class TestMaxPositions:
    def test_can_open_respects_limit(self, pm):
        _mock_config.MAX_POSITIONS = 2

        pm.open_position("A", "A", 1.0, 100, 0.1)
        assert pm.can_open_position() is True
        pm.open_position("B", "B", 1.0, 100, 0.1)
        assert pm.can_open_position() is False


# ────────────────────────── persistence ──────────────────────────

class TestPersistence:
    def test_positions_survive_reload(self, tmp_path):
        pm1 = PositionManager(data_dir=str(tmp_path))
        pm1.open_position("AAAA", "TEST", 1.0, 100, 0.5)
        assert pm1.get_position_count() == 1

        pm2 = PositionManager(data_dir=str(tmp_path))
        assert pm2.get_position_count() == 1
        pos = pm2.get_position_by_token("AAAA")
        assert pos is not None
        assert pos.entry_price == 1.0


# ────────────────────────── bulk price update ──────────────────────────

class TestBulkUpdate:
    def test_update_all_prices(self, pm):
        pm.open_position("A", "A", 1.0, 100, 0.1)
        pm.open_position("B", "B", 2.0, 50, 0.2)
        pm.update_all_prices({"A": 1.5, "B": 1.8})
        assert pm.get_position_by_token("A").current_price == 1.5
        assert pm.get_position_by_token("B").current_price == 1.8
