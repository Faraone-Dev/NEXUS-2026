"""
Tests for ReactiveAI weight adjustment system
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from ai.reactive import ReactiveAI, RealtimeWeights, TradeOutcome


@pytest.fixture
def tmp_weights(tmp_path):
    """Provide temp paths so tests don't touch real data."""
    weights_file = tmp_path / "reactive_weights.json"
    history_file = tmp_path / "trade_outcomes.json"
    return weights_file, history_file


@pytest.fixture
def reactive(tmp_weights):
    """Fresh ReactiveAI with temp storage."""
    weights_file, history_file = tmp_weights
    ai = ReactiveAI.__new__(ReactiveAI)
    ai.WEIGHTS_FILE = weights_file
    ai.HISTORY_FILE = history_file
    ai.weights = RealtimeWeights()
    ai.outcomes_history = []
    return ai


def _make_outcome(**overrides) -> TradeOutcome:
    defaults = dict(
        token_mint="AAAA1111",
        pnl_percent=10.0,
        hold_time_hours=2.0,
        entry_liquidity=100_000,
        entry_holders=200,
        entry_age_hours=12.0,
        entry_volume=50_000,
        token_score=75,
        sentiment_score=70,
        risk_score=80,
        confidence=80,
        had_whale_signal=False,
        whale_was_buying=False,
    )
    defaults.update(overrides)
    return TradeOutcome(**defaults)


# ────────────────────────── weight bounds ──────────────────────────

class TestClampWeights:
    def test_weights_stay_within_bounds_after_wins(self, reactive):
        """Repeated wins must never push weights outside clamp range."""
        for _ in range(50):
            reactive.learn_from_trade(_make_outcome(pnl_percent=80.0))

        w = reactive.weights
        assert 0.3 <= w.liquidity_weight <= 3.0
        assert 0.5 <= w.token_analyzer_trust <= 2.0
        assert 0.5 <= w.sentiment_trust <= 2.0
        assert 0.5 <= w.risk_trust <= 2.0
        assert 5 <= w.base_stop_loss <= 30
        assert 20 <= w.base_take_profit <= 100
        assert 0.5 <= w.position_size_multiplier <= 2.0

    def test_weights_stay_within_bounds_after_losses(self, reactive):
        """Repeated losses must never push weights outside clamp range."""
        for _ in range(50):
            reactive.learn_from_trade(_make_outcome(pnl_percent=-40.0))

        w = reactive.weights
        assert 0.3 <= w.liquidity_weight <= 3.0
        assert 0.5 <= w.token_analyzer_trust <= 2.0
        assert 0.5 <= w.risk_trust <= 2.0
        assert 5 <= w.base_stop_loss <= 30
        assert 0.5 <= w.position_size_multiplier <= 2.0


# ────────────────────────── learning direction ──────────────────────────

class TestLearningDirection:
    def test_win_increases_agent_trust(self, reactive):
        """A big win with high agent scores should increase trust."""
        before = reactive.weights.token_analyzer_trust
        reactive.learn_from_trade(_make_outcome(
            pnl_percent=30.0, token_score=90, sentiment_score=90, risk_score=90
        ))
        assert reactive.weights.token_analyzer_trust > before

    def test_loss_decreases_agent_trust(self, reactive):
        """A loss with high agent scores should decrease trust."""
        before = reactive.weights.token_analyzer_trust
        reactive.learn_from_trade(_make_outcome(
            pnl_percent=-20.0, token_score=90, sentiment_score=90, risk_score=90
        ))
        assert reactive.weights.token_analyzer_trust < before

    def test_win_increases_position_size(self, reactive):
        before = reactive.weights.position_size_multiplier
        reactive.learn_from_trade(_make_outcome(pnl_percent=25.0))
        assert reactive.weights.position_size_multiplier > before

    def test_loss_decreases_position_size(self, reactive):
        before = reactive.weights.position_size_multiplier
        reactive.learn_from_trade(_make_outcome(pnl_percent=-25.0))
        assert reactive.weights.position_size_multiplier < before

    def test_whale_buy_win_boosts_whale_weight(self, reactive):
        before = reactive.weights.whale_signal_weight
        reactive.learn_from_trade(_make_outcome(
            pnl_percent=20.0, had_whale_signal=True, whale_was_buying=True
        ))
        assert reactive.weights.whale_signal_weight > before

    def test_whale_buy_loss_reduces_whale_weight(self, reactive):
        before = reactive.weights.whale_signal_weight
        reactive.learn_from_trade(_make_outcome(
            pnl_percent=-15.0, had_whale_signal=True, whale_was_buying=True
        ))
        assert reactive.weights.whale_signal_weight < before


# ────────────────────────── stats tracking ──────────────────────────

class TestStatsTracking:
    def test_win_count(self, reactive):
        reactive.learn_from_trade(_make_outcome(pnl_percent=10.0))
        reactive.learn_from_trade(_make_outcome(pnl_percent=-5.0))
        reactive.learn_from_trade(_make_outcome(pnl_percent=20.0))
        assert reactive.weights.wins == 2
        assert reactive.weights.losses == 1
        assert reactive.weights.total_trades == 3

    def test_pnl_accumulates(self, reactive):
        reactive.learn_from_trade(_make_outcome(pnl_percent=10.0))
        reactive.learn_from_trade(_make_outcome(pnl_percent=-5.0))
        assert reactive.weights.total_pnl == pytest.approx(5.0)

    def test_lr_decays_with_trades(self, reactive):
        """Learning rate should decay as trades accumulate."""
        lr_before = reactive._current_lr()
        for _ in range(20):
            reactive.learn_from_trade(_make_outcome(pnl_percent=5.0))
        lr_after = reactive._current_lr()
        assert lr_after < lr_before
        assert lr_after >= reactive.weights.learning_rate_floor

    def test_lr_never_below_floor(self, reactive):
        """Even after many trades, LR stays >= floor."""
        for _ in range(200):
            reactive.learn_from_trade(_make_outcome(pnl_percent=5.0))
        assert reactive._current_lr() >= reactive.weights.learning_rate_floor

    def test_early_trades_adjust_more(self, reactive):
        """First trade should move weights more than trade #50."""
        trust_before_1 = reactive.weights.token_analyzer_trust
        reactive.learn_from_trade(_make_outcome(pnl_percent=30.0, token_score=90))
        delta_early = reactive.weights.token_analyzer_trust - trust_before_1

        # Reset trust, simulate 50 trades then measure
        reactive2 = ReactiveAI.__new__(ReactiveAI)
        reactive2.WEIGHTS_FILE = reactive.WEIGHTS_FILE
        reactive2.HISTORY_FILE = reactive.HISTORY_FILE
        reactive2.weights = RealtimeWeights()
        reactive2.weights.total_trades = 50
        reactive2.outcomes_history = []

        trust_before_50 = reactive2.weights.token_analyzer_trust
        reactive2.learn_from_trade(_make_outcome(pnl_percent=30.0, token_score=90))
        delta_late = reactive2.weights.token_analyzer_trust - trust_before_50

        assert delta_early > delta_late


# ────────────────────────── score adjustment ──────────────────────────

class TestAdjustScores:
    def test_neutral_weights_pass_through(self, reactive):
        """With default weights (1.0), scores should pass through unchanged."""
        adj_t, adj_s, adj_r, bonus = reactive.adjust_scores(
            token_score=75, sentiment_score=70, risk_score=80,
            token_data={}
        )
        assert adj_t == 75
        assert adj_s == 70
        assert adj_r == 80
        assert bonus == 0

    def test_high_volume_bonus_applied(self, reactive):
        reactive.weights.high_volume_bonus = 10.0
        _, _, _, bonus = reactive.adjust_scores(
            token_score=75, sentiment_score=70, risk_score=80,
            token_data={"volume_24h": 200_000}
        )
        assert bonus == 10

    def test_whale_buy_signal_adds_bonus(self, reactive):
        reactive.weights.whale_signal_weight = 2.0
        _, _, _, bonus = reactive.adjust_scores(
            token_score=75, sentiment_score=70, risk_score=80,
            token_data={"whale_signal": "STRONG_BUY"}
        )
        assert bonus == 20  # 10 * 2.0

    def test_scores_clamped_0_100(self, reactive):
        reactive.weights.token_analyzer_trust = 2.0
        adj_t, _, _, _ = reactive.adjust_scores(
            token_score=90, sentiment_score=70, risk_score=80,
            token_data={}
        )
        assert adj_t <= 100


# ────────────────────────── persistence ──────────────────────────

class TestPersistence:
    def test_weights_saved_and_loaded(self, tmp_weights):
        weights_file, history_file = tmp_weights

        ai1 = ReactiveAI.__new__(ReactiveAI)
        ai1.WEIGHTS_FILE = weights_file
        ai1.HISTORY_FILE = history_file
        ai1.weights = RealtimeWeights()
        ai1.outcomes_history = []

        ai1.learn_from_trade(_make_outcome(pnl_percent=30.0, token_score=90))

        # Load into fresh instance
        ai2 = ReactiveAI.__new__(ReactiveAI)
        ai2.WEIGHTS_FILE = weights_file
        ai2.HISTORY_FILE = history_file
        ai2.weights = ai2._load_weights()
        ai2.outcomes_history = ai2._load_history()

        assert ai2.weights.total_trades == 1
        assert ai2.weights.wins == 1
        assert len(ai2.outcomes_history) == 1
