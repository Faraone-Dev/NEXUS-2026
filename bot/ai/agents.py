"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Agent Definitions                         ║
║                         Specialized analysis agents                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class Decision(Enum):
    """Trading decision"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    SKIP = "SKIP"


class RiskLevel(Enum):
    """Risk classification"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


@dataclass
class TokenAnalysis:
    """Output from Token Analyzer agent"""
    score: int  # 0-100
    liquidity_ok: bool
    volume_ok: bool
    holders_ok: bool
    age_ok: bool
    contract_safe: bool
    reasons: list[str]


@dataclass
class SentimentAnalysis:
    """Output from Sentiment Analyzer agent"""
    score: int  # 0-100
    hype_level: str  # "early", "building", "peak", "fading"
    social_mentions: int
    notable_wallets: bool
    trending: bool
    reasons: list[str]


@dataclass
class RiskAnalysis:
    """Output from Risk Assessor agent"""
    score: int  # 0-100 (higher = safer)
    rug_probability: float  # 0-1
    risk_level: RiskLevel
    red_flags: list[str]
    green_flags: list[str]


@dataclass
class TradingDecision:
    """Final output from Master Decision agent"""
    decision: Decision
    confidence: int  # 0-100
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    position_size_percent: float
    reasoning: str
    
    # Component scores
    token_score: int
    sentiment_score: int
    risk_score: int


# ═══════════════════════════════════════════════════════════════════════════════
#                              AGENT PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

class TokenAnalyzer:
    """
    Agent #1: Token Analyzer
    Analyzes token fundamentals and on-chain data
    """
    
    SYSTEM_PROMPT = """You are a Solana token analyzer. Analyze token data and rate quality 0-100.

ANALYZE:
1. Liquidity (min $50k for safety)
2. Volume (healthy = volume > 10% of liquidity)
3. Holder distribution (concentrated = risky)
4. Token age (new = more volatile)
5. Contract safety (freeze/mint authority = risky)

RESPOND WITH JSON ONLY:
{
    "score": 0-100,
    "liquidity_ok": true/false,
    "volume_ok": true/false,
    "holders_ok": true/false,
    "age_ok": true/false,
    "contract_safe": true/false,
    "reasons": ["reason1", "reason2"]
}"""

    @staticmethod
    def build_prompt(token_data: dict) -> str:
        """Build analysis prompt from token data"""
        return f"""Analyze this Solana token:

Symbol: {token_data.get('symbol', '???')}
Name: {token_data.get('name', 'Unknown')}
Price: ${token_data.get('price', 0):.8f}
Liquidity: ${token_data.get('liquidity', 0):,.0f}
Volume 24h: ${token_data.get('volume_24h', 0):,.0f}
Market Cap: ${token_data.get('market_cap', 0):,.0f}
Holders: {token_data.get('holder_count', 0):,}
Age: {token_data.get('age_hours', 0):.1f} hours
Top 10 Holders: {token_data.get('top_10_percent', 0):.1f}%
Has Freeze Authority: {token_data.get('has_freeze', False)}
Has Mint Authority: {token_data.get('has_mint', False)}

Rate this token 0-100 and explain."""


class SentimentAnalyzer:
    """
    Agent #2: Sentiment Analyzer
    Analyzes social sentiment and hype
    """
    
    SYSTEM_PROMPT = """You are a crypto sentiment analyzer. Detect hype and social momentum.

ANALYZE:
1. Hype stage: "early" (few mentions) | "building" (growing) | "peak" (everywhere) | "fading" (declining)
2. Social presence (Twitter mentions, Telegram groups)
3. Notable wallet activity (whales, influencers)
4. Trending status

RESPOND WITH JSON ONLY:
{
    "score": 0-100,
    "hype_level": "early|building|peak|fading",
    "social_mentions": number,
    "notable_wallets": true/false,
    "trending": true/false,
    "reasons": ["reason1", "reason2"]
}"""

    @staticmethod
    def build_prompt(sentiment_data: dict) -> str:
        """Build sentiment prompt"""
        return f"""Analyze social sentiment:

Token: {sentiment_data.get('symbol', '???')}
Twitter Mentions (24h): {sentiment_data.get('twitter_mentions', 0)}
Telegram Members: {sentiment_data.get('telegram_members', 0)}
Price Change 1h: {sentiment_data.get('price_change_1h', 0):+.1f}%
Price Change 24h: {sentiment_data.get('price_change_24h', 0):+.1f}%
Volume Spike: {sentiment_data.get('volume_spike', False)}
Notable Buys: {sentiment_data.get('notable_buys', [])}

Assess the sentiment and hype level."""


class RiskAssessor:
    """
    Agent #3: Risk Assessor
    Evaluates rug pull probability and risks
    """
    
    SYSTEM_PROMPT = """You are a crypto risk analyst. Assess rug pull probability and risks.

RED FLAGS (increase rug probability):
- Mint authority enabled (can print tokens)
- Freeze authority (can freeze your tokens)
- Top holder owns >20%
- Very low liquidity (<$20k)
- Anonymous team
- No socials/website
- Copy of existing token name

GREEN FLAGS (lower risk):
- Liquidity locked
- Contract verified
- Active community
- Established DEX listing
- High holder count (>1000)

RESPOND WITH JSON ONLY:
{
    "score": 0-100,
    "rug_probability": 0.0-1.0,
    "risk_level": "LOW|MEDIUM|HIGH|EXTREME",
    "red_flags": ["flag1", "flag2"],
    "green_flags": ["flag1", "flag2"]
}"""

    @staticmethod
    def build_prompt(risk_data: dict) -> str:
        """Build risk assessment prompt"""
        return f"""Assess rug pull risk:

Token: {risk_data.get('symbol', '???')}
Has Mint Authority: {risk_data.get('has_mint', False)}
Has Freeze Authority: {risk_data.get('has_freeze', False)}
Top Holder %: {risk_data.get('top_holder_percent', 0):.1f}%
Top 10 Holders %: {risk_data.get('top_10_percent', 0):.1f}%
Liquidity: ${risk_data.get('liquidity', 0):,.0f}
Liquidity Locked: {risk_data.get('liquidity_locked', False)}
Contract Verified: {risk_data.get('verified', False)}
Holder Count: {risk_data.get('holder_count', 0):,}
Age: {risk_data.get('age_hours', 0):.1f} hours
Has Website: {risk_data.get('has_website', False)}
Has Twitter: {risk_data.get('has_twitter', False)}

Evaluate the rug pull probability."""


class MasterDecision:
    """
    Agent #4: Master Decision
    Combines all analyses and makes final trading decision
    """
    
    SYSTEM_PROMPT = """You are the NEXUS master trading AI. Make final trading decisions.

INPUT: Scores from 3 specialized agents
- Token Analyzer (fundamentals)
- Sentiment Analyzer (social/hype)  
- Risk Assessor (safety)

DECISION RULES:
1. If risk_score < 50: SKIP (too risky)
2. If token_score < 60: SKIP (poor fundamentals)
3. If all scores > 70 AND sentiment = "building": BUY
4. If sentiment = "peak" AND price_change_24h > 100%: Consider SELL
5. If TA composite signal = BEARISH with confidence > 70%: SKIP or reduce position
6. If TA composite signal = BULLISH and trend = uptrend: boost confidence +10
7. Otherwise: HOLD or SKIP

POSITION SIZING:
- High confidence (>85): 5% of portfolio
- Medium confidence (70-85): 3% of portfolio
- Lower confidence: 1% or skip

RESPOND WITH JSON ONLY:
{
    "decision": "BUY|SELL|HOLD|SKIP",
    "confidence": 0-100,
    "entry_price": number or null,
    "stop_loss": number or null,
    "take_profit": number or null,
    "position_size_percent": number,
    "reasoning": "Brief explanation max 100 words"
}"""

    @staticmethod
    def build_prompt(
        token_analysis: TokenAnalysis,
        sentiment_analysis: SentimentAnalysis,
        risk_analysis: RiskAnalysis,
        current_price: float,
        ta_data: Optional[dict] = None
    ) -> str:
        """Build master decision prompt"""
        prompt = f"""Make trading decision based on agent analyses:

═══ TOKEN ANALYSIS ═══
Score: {token_analysis.score}/100
Liquidity OK: {token_analysis.liquidity_ok}
Volume OK: {token_analysis.volume_ok}
Contract Safe: {token_analysis.contract_safe}
Reasons: {', '.join(token_analysis.reasons)}

═══ SENTIMENT ANALYSIS ═══
Score: {sentiment_analysis.score}/100
Hype Level: {sentiment_analysis.hype_level}
Trending: {sentiment_analysis.trending}
Notable Wallets: {sentiment_analysis.notable_wallets}
Reasons: {', '.join(sentiment_analysis.reasons)}

═══ RISK ANALYSIS ═══
Score: {risk_analysis.score}/100
Rug Probability: {risk_analysis.rug_probability:.1%}
Risk Level: {risk_analysis.risk_level.value}
Red Flags: {', '.join(risk_analysis.red_flags)}
Green Flags: {', '.join(risk_analysis.green_flags)}

═══ CURRENT PRICE ═══
${current_price:.8f}"""

        if ta_data and ta_data.get("ta_signal"):
            prompt += f"""

═══ TECHNICAL ANALYSIS (MCP Signals) ═══
Composite Signal: {ta_data.get('ta_signal', 'N/A').upper()}
Signal Confidence: {ta_data.get('ta_confidence', 0):.0%}
Price: ${ta_data.get('ta_price', 0):,.2f}
Bullish Signals: {ta_data.get('ta_bullish_count', 0)} | Bearish: {ta_data.get('ta_bearish_count', 0)}
RSI: {ta_data.get('ta_rsi', 'N/A')}
Indicators: {ta_data.get('ta_indicators_summary', 'N/A')}"""

        prompt += "\n\nMake your decision. If BUY, set SL at -15% and TP at +50%."
        return prompt
