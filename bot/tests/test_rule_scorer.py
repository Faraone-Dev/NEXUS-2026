"""Tests for ai/rule_scorer.py — deterministic rule-based scorer."""

import pytest
from ai.rule_scorer import rule_based_score


# ── helpers ──────────────────────────────────────────────────────────────────
def _base_data(**overrides) -> dict:
    """Sensible defaults that score ~BUY."""
    d = dict(
        price=0.0001,
        market_cap=500_000,
        liquidity=80_000,
        volume_24h=120_000,
        volume_1h=8_000,
        buys_24h=500,
        sells_24h=300,
        buy_sell_ratio=1.67,
        volume_spike=False,
        price_change_1h=12,
        price_change_6h=20,
        price_change_24h=35,
        security_score=75,
        has_mint=False,
        has_freeze=False,
        holder_count=800,
        top_holder_percent=8,
        age_hours=6,
        whale_signal="NEUTRAL",
        whale_buys=0,
        whale_sells=0,
        ta_signal="",
        ta_confidence=0,
    )
    d.update(overrides)
    return d


# ═══════════════════════════════════════════════════════════════════════════
#  Hard-skip rules
# ═══════════════════════════════════════════════════════════════════════════
class TestHardSkip:
    def test_mint_authority_instant_skip(self):
        r = rule_based_score(_base_data(has_mint=True))
        assert r.decision == "SKIP"
        assert r.score == 0

    def test_dead_volume_instant_skip(self):
        r = rule_based_score(_base_data(volume_24h=5_000))
        assert r.decision == "SKIP"
        assert r.score <= 10

    def test_top_holder_50pct_instant_skip(self):
        r = rule_based_score(_base_data(top_holder_percent=55))
        assert r.decision == "SKIP"


# ═══════════════════════════════════════════════════════════════════════════
#  Buy signals
# ═══════════════════════════════════════════════════════════════════════════
class TestBuySignals:
    def test_strong_token_buys(self):
        r = rule_based_score(_base_data())
        assert r.decision == "BUY"
        assert r.score >= 60

    def test_whale_buy_boosts_score(self):
        base = rule_based_score(_base_data())
        whale = rule_based_score(_base_data(whale_signal="STRONG_BUY"))
        assert whale.score > base.score

    def test_volume_spike_boosts_score(self):
        base = rule_based_score(_base_data())
        spike = rule_based_score(_base_data(volume_spike=True))
        assert spike.score > base.score

    def test_ta_bullish_boosts_score(self):
        base = rule_based_score(_base_data())
        ta = rule_based_score(_base_data(ta_signal="BULLISH", ta_confidence=0.8))
        assert ta.score > base.score


# ═══════════════════════════════════════════════════════════════════════════
#  Negative signals
# ═══════════════════════════════════════════════════════════════════════════
class TestNegativeSignals:
    def test_selling_pressure_hurts(self):
        base = rule_based_score(_base_data())
        weak = rule_based_score(_base_data(buy_sell_ratio=0.5))
        assert weak.score < base.score
        assert any("Sell" in s for s in weak.reasons_skip)

    def test_dumping_price_hurts(self):
        r = rule_based_score(_base_data(price_change_1h=-25))
        assert any("Dumping" in s for s in r.reasons_skip)

    def test_whale_sell_hurts(self):
        base = rule_based_score(_base_data())
        sell = rule_based_score(_base_data(whale_signal="STRONG_SELL"))
        assert sell.score < base.score

    def test_low_security_hurts(self):
        base = rule_based_score(_base_data())
        low = rule_based_score(_base_data(security_score=25))
        assert low.score < base.score


# ═══════════════════════════════════════════════════════════════════════════
#  Edge cases
# ═══════════════════════════════════════════════════════════════════════════
class TestEdgeCases:
    def test_score_clamped_0_100(self):
        # Maximally good token
        r = rule_based_score(_base_data(
            volume_24h=1_000_000, buy_sell_ratio=3.0, volume_spike=True,
            whale_signal="STRONG_BUY", ta_signal="BULLISH", ta_confidence=0.9,
            security_score=90, holder_count=5000, price_change_1h=20,
        ))
        assert 0 <= r.score <= 100

    def test_reasons_populated(self):
        r = rule_based_score(_base_data())
        assert len(r.reasons_buy) > 0

    def test_deterministic(self):
        d = _base_data()
        r1 = rule_based_score(d)
        r2 = rule_based_score(d)
        assert r1.score == r2.score
        assert r1.decision == r2.decision
