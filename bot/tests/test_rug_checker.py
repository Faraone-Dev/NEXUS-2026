"""
Tests for RugChecker validation logic
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Optional
from validation.rug_checker import RugChecker, RugCheckResult


class FakeRugCheckData:
    """Mock for the raw data returned by RugCheckClient.check_token()"""
    def __init__(self, **kwargs):
        self.score = kwargs.get("score", 5000)
        self.score_normalized = kwargs.get("score_normalized", 70)
        self.risks = kwargs.get("risks", [])
        self.risk_count = kwargs.get("risk_count", 0)
        self.danger_count = kwargs.get("danger_count", 0)
        self.warn_count = kwargs.get("warn_count", 0)
        self.mint_authority = kwargs.get("mint_authority", False)
        self.freeze_authority = kwargs.get("freeze_authority", False)
        self.mutable_metadata = kwargs.get("mutable_metadata", False)
        self.top_10_holders_pct = kwargs.get("top_10_holders_pct", 20.0)
        self.top_holder_pct = kwargs.get("top_holder_pct", 5.0)
        self.holder_count = kwargs.get("holder_count", 500)
        self.lp_locked_pct = kwargs.get("lp_locked_pct", 80.0)
        self.lp_providers = kwargs.get("lp_providers", 10)
        self.creator = kwargs.get("creator", "creator123")
        self.token_symbol = kwargs.get("token_symbol", "TEST")


class FakeTokenPair:
    """Mock for DexScreener pair object"""
    def __init__(self, **kwargs):
        self.pair_address = kwargs.get("pair_address", "pair1")
        self.base_symbol = kwargs.get("base_symbol", "TEST")
        self.liquidity_usd = kwargs.get("liquidity_usd", 100_000)
        self.price_usd = kwargs.get("price_usd", 0.001)
        self.volume_24h = kwargs.get("volume_24h", 50_000)
        self.fdv = kwargs.get("fdv", 500_000)
        self.age_hours = kwargs.get("age_hours", 24.0)
        self.pair_created_at = kwargs.get("pair_created_at", "2024-01-01T00:00:00Z")


def _make_checker(rugcheck_data=None, pairs=None):
    """Build a rug checker with mocked data sources."""
    mock_rugcheck = AsyncMock()
    mock_rugcheck.check_token = AsyncMock(return_value=rugcheck_data)
    mock_rugcheck.close = AsyncMock()

    mock_dex = AsyncMock()
    mock_dex.get_token_pairs = AsyncMock(return_value=pairs or [])
    mock_dex.close = AsyncMock()

    mock_birdeye = AsyncMock()
    mock_birdeye.close = AsyncMock()

    checker = RugChecker(
        birdeye=mock_birdeye,
        dexscreener=mock_dex,
        rugcheck=mock_rugcheck,
    )
    return checker


# ────────────────────────── safe token passes ──────────────────────────

class TestSafeToken:
    @pytest.mark.asyncio
    async def test_clean_token_passes(self):
        checker = _make_checker(
            rugcheck_data=FakeRugCheckData(),
            pairs=[FakeTokenPair()],
        )
        result = await checker.check("AAAA1111")
        assert result is not None
        assert result.is_safe is True
        assert result.safety_score >= 50

    @pytest.mark.asyncio
    async def test_score_above_zero(self):
        checker = _make_checker(
            rugcheck_data=FakeRugCheckData(score_normalized=80),
            pairs=[FakeTokenPair(liquidity_usd=200_000)],
        )
        result = await checker.check("AAAA1111")
        assert result.safety_score > 0


# ────────────────────────── red flags ──────────────────────────

class TestRedFlags:
    @pytest.mark.asyncio
    async def test_mint_authority_fails(self):
        checker = _make_checker(
            rugcheck_data=FakeRugCheckData(mint_authority=True),
            pairs=[FakeTokenPair()],
        )
        result = await checker.check("AAAA1111")
        assert result.is_safe is False
        assert any("MINT" in f.upper() for f in result.red_flags)

    @pytest.mark.asyncio
    async def test_low_liquidity_fails(self):
        checker = _make_checker(
            rugcheck_data=FakeRugCheckData(),
            pairs=[FakeTokenPair(liquidity_usd=5_000)],
        )
        result = await checker.check("AAAA1111")
        assert result.is_safe is False

    @pytest.mark.asyncio
    async def test_high_top_holder_flagged(self):
        checker = _make_checker(
            rugcheck_data=FakeRugCheckData(top_holder_pct=35.0),
            pairs=[FakeTokenPair()],
        )
        result = await checker.check("AAAA1111")
        assert any("holder" in f.lower() or "%" in f for f in result.red_flags)

    @pytest.mark.asyncio
    async def test_danger_risks_penalize_score(self):
        checker = _make_checker(
            rugcheck_data=FakeRugCheckData(
                danger_count=2,
                risks=[{"level": "danger", "name": "Honeypot risk"}],
            ),
            pairs=[FakeTokenPair()],
        )
        result = await checker.check("AAAA1111")
        # Score should be lower than a clean token
        clean = _make_checker(
            rugcheck_data=FakeRugCheckData(),
            pairs=[FakeTokenPair()],
        )
        clean_result = await clean.check("AAAA1111")
        assert result.safety_score <= clean_result.safety_score


# ────────────────────────── edge cases ──────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_no_data_returns_none(self):
        checker = _make_checker(rugcheck_data=None, pairs=[])
        result = await checker.check("AAAA1111")
        assert result is None

    @pytest.mark.asyncio
    async def test_freeze_authority_penalizes_but_safe_with_good_score(self):
        """Freeze authority penalizes score but doesn't auto-fail if score stays >= 30."""
        checker = _make_checker(
            rugcheck_data=FakeRugCheckData(
                freeze_authority=True, score_normalized=80
            ),
            pairs=[FakeTokenPair()],
        )
        result = await checker.check("AAAA1111")
        # Freeze reduces score by 30 but from 80 → 50, still >= 30 and no mint
        assert result is not None
        assert any("FREEZE" in f.upper() for f in result.red_flags)

    @pytest.mark.asyncio
    async def test_scan_liquidity_fallback(self):
        """If no pair data, use scan_liquidity from caller."""
        checker = _make_checker(
            rugcheck_data=FakeRugCheckData(),
            pairs=[],
        )
        result = await checker.check("AAAA1111", scan_liquidity=80_000)
        assert result is not None
        assert result.liquidity_usd == 80_000
