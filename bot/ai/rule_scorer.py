"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                      NEXUS AI - Rule-Based Scorer                             ║
║            Deterministic scoring baseline for A/B testing vs LLM             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Pure rule-based scorer — no LLM calls, no randomness.
Used as a baseline to measure whether DeepSeek adds alpha over simple heuristics.
"""

from dataclasses import dataclass
from loguru import logger


@dataclass
class RuleDecision:
    """Output of the rule-based scorer."""
    decision: str          # "BUY" or "SKIP"
    score: int             # 0-100 composite score
    confidence: int        # 0-100
    reasons_buy: list[str]
    reasons_skip: list[str]


def rule_based_score(data: dict) -> RuleDecision:
    """
    Deterministic token scorer.
    
    Returns BUY if score >= 60 and no hard-skip flags.
    Every rule is explicit — no LLM hallucination.
    """
    score = 50  # neutral baseline
    reasons_buy = []
    reasons_skip = []

    # ───────────────────── HARD SKIP (instant reject) ─────────────────────
    if data.get("has_mint", False):
        return RuleDecision("SKIP", 0, 95, [], ["Mint authority active"])

    if data.get("has_freeze", False):
        score -= 15
        reasons_skip.append("Freeze authority active")

    volume_24h = data.get("volume_24h", 0)
    if volume_24h < 10_000:
        return RuleDecision("SKIP", 10, 90, [], ["Volume < $10k (dead token)"])

    top_holder = data.get("top_holder_percent", 0)
    if top_holder > 50:
        return RuleDecision("SKIP", 5, 90, [], [f"Top holder owns {top_holder:.0f}%"])

    # ───────────────────── POSITIVE SIGNALS ─────────────────────
    # Volume
    if volume_24h > 100_000:
        score += 10
        reasons_buy.append(f"Strong volume ${volume_24h:,.0f}")
    elif volume_24h > 50_000:
        score += 5
        reasons_buy.append(f"Decent volume ${volume_24h:,.0f}")

    # Buy/sell pressure
    buy_sell = data.get("buy_sell_ratio", 0)
    if buy_sell > 1.5:
        score += 10
        reasons_buy.append(f"Strong buying pressure ({buy_sell:.1f}x)")
    elif buy_sell > 1.2:
        score += 5
        reasons_buy.append(f"Buy pressure ({buy_sell:.1f}x)")
    elif buy_sell < 0.7:
        score -= 10
        reasons_skip.append(f"Sell pressure ({buy_sell:.1f}x)")

    # Volume spike
    if data.get("volume_spike", False):
        score += 8
        reasons_buy.append("1h volume spike detected")

    # Price momentum
    change_1h = data.get("price_change_1h", 0)
    if 5 < change_1h < 50:
        score += 8
        reasons_buy.append(f"Healthy momentum +{change_1h:.0f}%/1h")
    elif change_1h > 50:
        score -= 5
        reasons_skip.append(f"Overextended +{change_1h:.0f}%/1h")
    elif change_1h < -15:
        score -= 8
        reasons_skip.append(f"Dumping {change_1h:.0f}%/1h")

    # Security score
    sec_score = data.get("security_score", 50)
    if sec_score >= 70:
        score += 8
        reasons_buy.append(f"Good security ({sec_score}/100)")
    elif sec_score < 40:
        score -= 10
        reasons_skip.append(f"Low security ({sec_score}/100)")

    # Liquidity
    liquidity = data.get("liquidity", 0)
    if liquidity > 100_000:
        score += 5
        reasons_buy.append(f"Good liquidity ${liquidity:,.0f}")
    elif liquidity < 20_000:
        score -= 8
        reasons_skip.append(f"Low liquidity ${liquidity:,.0f}")

    # Holder distribution
    holders = data.get("holder_count", 0)
    if holders > 500:
        score += 5
        reasons_buy.append(f"Healthy holders ({holders:,})")
    elif holders < 50:
        score -= 5
        reasons_skip.append(f"Few holders ({holders})")

    if top_holder > 25:
        score -= 8
        reasons_skip.append(f"Top holder {top_holder:.0f}%")
    elif top_holder < 10:
        score += 3
        reasons_buy.append(f"Distributed ownership ({top_holder:.0f}%)")

    # Token age (sweet spot: 1-48h for memecoins)
    age = data.get("age_hours", 999)
    if 1 < age < 48:
        score += 5
        reasons_buy.append(f"Good age ({age:.0f}h)")
    elif age < 0.5:
        score -= 5
        reasons_skip.append(f"Too new ({age*60:.0f}min)")

    # Whale signal
    whale = data.get("whale_signal", "UNAVAILABLE")
    if whale in ("BUY", "STRONG_BUY"):
        score += 10
        reasons_buy.append(f"Whale signal: {whale}")
    elif whale in ("SELL", "STRONG_SELL"):
        score -= 10
        reasons_skip.append(f"Whale signal: {whale}")

    # TA signal (if available)
    ta = data.get("ta_signal", "")
    ta_conf = data.get("ta_confidence", 0)
    if ta and ta_conf > 0.6:
        if ta.upper() in ("BULLISH", "BUY"):
            score += 7
            reasons_buy.append(f"TA: {ta} ({ta_conf:.0%})")
        elif ta.upper() in ("BEARISH", "SELL"):
            score -= 7
            reasons_skip.append(f"TA: {ta} ({ta_conf:.0%})")

    # ───────────────────── DECISION ─────────────────────
    score = max(0, min(100, score))
    decision = "BUY" if score >= 60 and not data.get("has_mint", False) else "SKIP"
    confidence = min(95, abs(score - 50) * 2)

    return RuleDecision(
        decision=decision,
        score=score,
        confidence=confidence,
        reasons_buy=reasons_buy,
        reasons_skip=reasons_skip,
    )
