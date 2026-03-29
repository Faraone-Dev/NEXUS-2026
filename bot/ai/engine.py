"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Engine                                    ║
║                    DeepSeek multi-agent orchestrator                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
from functools import partial
from typing import Optional

from loguru import logger

try:  # pragma: no cover - Async client not always available
    from openai import AsyncOpenAI as _AsyncOpenAI
except ImportError:  # pragma: no cover - fallback to sync client
    _AsyncOpenAI = None

from openai import OpenAI

from config import config
from .agents import (
    TokenAnalyzer, SentimentAnalyzer, RiskAssessor, MasterDecision,
    TokenAnalysis, SentimentAnalysis, RiskAnalysis, TradingDecision,
    Decision, RiskLevel
)


class AIEngine:
    """
    Multi-Agent AI Engine
    
    Orchestrates 4 specialized agents:
    1. Token Analyzer - Fundamentals
    2. Sentiment Analyzer - Social/Hype
    3. Risk Assessor - Safety
    4. Master Decision - Final call
    """
    
    def __init__(self):
        self.model = "deepseek-chat"
        self._async_client = bool(_AsyncOpenAI)
        if self._async_client:
            self.client = _AsyncOpenAI(
                api_key=config.DEEPSEEK_API_KEY,
                base_url=config.DEEPSEEK_BASE_URL
            )
        else:
            self.client = OpenAI(
                api_key=config.DEEPSEEK_API_KEY,
                base_url=config.DEEPSEEK_BASE_URL
            )
        logger.info("🤖 AI Engine initialized (DeepSeek multi-agent)")

    def _extract_json(self, text: str) -> dict:
        """Normalize model output into JSON payload."""
        payload = text.strip()
        if "```json" in payload:
            payload = payload.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in payload:
            payload = payload.split("```", 1)[1].split("```", 1)[0]
        return json.loads(payload)

    def _call_agent_sync(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        """Blocking fallback used when async client unavailable."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500,
                timeout=10
            )
            return self._extract_json(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"Agent call error: {e}")
            return None

    async def _call_agent(self, system_prompt: str, user_prompt: str) -> Optional[dict]:
        """Async agent invocation that keeps the event loop responsive."""
        if self._async_client:
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    max_tokens=500,
                    timeout=10
                )
                return self._extract_json(response.choices[0].message.content)
            except json.JSONDecodeError as e:  # pragma: no cover - network dependent
                logger.error(f"JSON parse error: {e}")
                return None
            except Exception as e:  # pragma: no cover - network dependent
                logger.error(f"Agent call error: {e}")
                return None

        loop = asyncio.get_running_loop()
        call = partial(self._call_agent_sync, system_prompt, user_prompt)
        return await loop.run_in_executor(None, call)
    
    async def analyze_token(self, token_data: dict) -> Optional[TokenAnalysis]:
        """
        Run Token Analyzer agent
        
        Args:
            token_data: Token metrics dict
            
        Returns:
            TokenAnalysis or None
        """
        logger.info("🔍 Agent #1: Token Analyzer...")
        
        prompt = TokenAnalyzer.build_prompt(token_data)
        result = await self._call_agent(TokenAnalyzer.SYSTEM_PROMPT, prompt)
        
        if not result:
            return None
        
        return TokenAnalysis(
            score=result.get("score", 0),
            liquidity_ok=result.get("liquidity_ok", False),
            volume_ok=result.get("volume_ok", False),
            holders_ok=result.get("holders_ok", False),
            age_ok=result.get("age_ok", False),
            contract_safe=result.get("contract_safe", False),
            reasons=result.get("reasons", [])
        )
    
    async def analyze_sentiment(self, sentiment_data: dict) -> Optional[SentimentAnalysis]:
        """
        Run Sentiment Analyzer agent
        
        Args:
            sentiment_data: Social/sentiment metrics
            
        Returns:
            SentimentAnalysis or None
        """
        logger.info("📊 Agent #2: Sentiment Analyzer...")
        
        prompt = SentimentAnalyzer.build_prompt(sentiment_data)
        result = await self._call_agent(SentimentAnalyzer.SYSTEM_PROMPT, prompt)
        
        if not result:
            return None
        
        return SentimentAnalysis(
            score=result.get("score", 0),
            hype_level=result.get("hype_level", "early"),
            social_mentions=result.get("social_mentions", 0),
            notable_wallets=result.get("notable_wallets", False),
            trending=result.get("trending", False),
            reasons=result.get("reasons", [])
        )
    
    async def analyze_risk(self, risk_data: dict) -> Optional[RiskAnalysis]:
        """
        Run Risk Assessor agent
        
        Args:
            risk_data: Risk metrics
            
        Returns:
            RiskAnalysis or None
        """
        logger.info("⚠️ Agent #3: Risk Assessor...")
        
        prompt = RiskAssessor.build_prompt(risk_data)
        result = await self._call_agent(RiskAssessor.SYSTEM_PROMPT, prompt)
        
        if not result:
            return None
        
        risk_level_str = result.get("risk_level", "HIGH")
        try:
            risk_level = RiskLevel[risk_level_str]
        except KeyError:
            risk_level = RiskLevel.HIGH
        
        return RiskAnalysis(
            score=result.get("score", 0),
            rug_probability=result.get("rug_probability", 0.5),
            risk_level=risk_level,
            red_flags=result.get("red_flags", []),
            green_flags=result.get("green_flags", [])
        )
    
    async def make_decision(
        self,
        token_analysis: TokenAnalysis,
        sentiment_analysis: SentimentAnalysis,
        risk_analysis: RiskAnalysis,
        current_price: float,
        ta_data: Optional[dict] = None
    ) -> Optional[TradingDecision]:
        """
        Run Master Decision agent
        
        Args:
            token_analysis: From Token Analyzer
            sentiment_analysis: From Sentiment Analyzer
            risk_analysis: From Risk Assessor
            current_price: Current token price
            
        Returns:
            TradingDecision or None
        """
        logger.info("🎯 Agent #4: Master Decision...")
        
        prompt = MasterDecision.build_prompt(
            token_analysis, sentiment_analysis, risk_analysis, current_price, ta_data
        )
        result = await self._call_agent(MasterDecision.SYSTEM_PROMPT, prompt)
        
        if not result:
            return None
        
        decision_str = result.get("decision", "SKIP")
        try:
            decision = Decision[decision_str]
        except KeyError:
            decision = Decision.SKIP
        
        return TradingDecision(
            decision=decision,
            confidence=result.get("confidence", 0),
            entry_price=result.get("entry_price"),
            stop_loss=result.get("stop_loss"),
            take_profit=result.get("take_profit"),
            position_size_percent=result.get("position_size_percent", 0),
            reasoning=result.get("reasoning", ""),
            token_score=token_analysis.score,
            sentiment_score=sentiment_analysis.score,
            risk_score=risk_analysis.score
        )
    
    async def full_analysis(self, all_data: dict) -> Optional[TradingDecision]:
        """
        Run complete 4-agent analysis pipeline
        
        Args:
            all_data: Combined token, sentiment, risk data
            
        Returns:
            TradingDecision or None
        """
        logger.info("═" * 50)
        logger.info(f"🚀 NEXUS Full Analysis: {all_data.get('symbol', '???')}")
        logger.info("═" * 50)
        
        # Agent 1: Token Analysis
        token_analysis = await self.analyze_token(all_data)
        if not token_analysis:
            logger.error("Token analysis failed")
            return None
        logger.info(f"   Token Score: {token_analysis.score}/100")
        
        # Agent 2: Sentiment Analysis
        sentiment_analysis = await self.analyze_sentiment(all_data)
        if not sentiment_analysis:
            logger.error("Sentiment analysis failed")
            return None
        logger.info(f"   Sentiment Score: {sentiment_analysis.score}/100 ({sentiment_analysis.hype_level})")
        
        # Agent 3: Risk Analysis
        risk_analysis = await self.analyze_risk(all_data)
        if not risk_analysis:
            logger.error("Risk analysis failed")
            return None
        logger.info(f"   Risk Score: {risk_analysis.score}/100 (Rug: {risk_analysis.rug_probability:.0%})")
        
        # Agent 4: Master Decision
        # Extract TA data if available (injected by Aarna MCP)
        ta_data = {k: v for k, v in all_data.items() if k.startswith("ta_")} or None
        
        decision = await self.make_decision(
            token_analysis,
            sentiment_analysis,
            risk_analysis,
            all_data.get("price", 0),
            ta_data=ta_data
        )
        
        if decision:
            logger.info("─" * 50)
            logger.info(f"📋 DECISION: {decision.decision.value}")
            logger.info(f"   Confidence: {decision.confidence}%")
            logger.info(f"   Reasoning: {decision.reasoning}")
            logger.info("═" * 50)
        
        return decision
    
    async def fast_analysis(self, all_data: dict) -> Optional[TradingDecision]:
        """
        FAST MODE: Single AI call with COMPREHENSIVE data.
        Gives AI ALL available information for best decisions.
        """
        symbol = all_data.get('symbol', '???')
        logger.info(f"⚡ FAST Analysis: {symbol}")
        
        # Build comprehensive prompt with ALL data
        prompt = f"""Analyze this Solana token for trading opportunity:

═══════════════════════════════════════════════════════════════
                    TOKEN: {symbol}
═══════════════════════════════════════════════════════════════

📊 MARKET DATA:
   Price: ${all_data.get('price', 0):.10f}
   FDV/Market Cap: ${all_data.get('market_cap', 0):,.0f}
   Liquidity: ${all_data.get('liquidity', 0):,.0f}
   
📈 VOLUME & ACTIVITY:
   Volume 24h: ${all_data.get('volume_24h', 0):,.0f}
   Volume 1h: ${all_data.get('volume_1h', 0):,.0f}
   Buys 24h: {all_data.get('buys_24h', 0):,}
   Sells 24h: {all_data.get('sells_24h', 0):,}
   Buy/Sell Ratio: {all_data.get('buys_24h', 0) / max(1, all_data.get('sells_24h', 1)):.2f}
   
📉 PRICE TRENDS:
   1h Change: {all_data.get('price_change_1h', 0):+.1f}%
   6h Change: {all_data.get('price_change_6h', 0):+.1f}%
   24h Change: {all_data.get('price_change_24h', 0):+.1f}%
   Volatility: {all_data.get('volatility', 0):.1f}%
   
🔐 SECURITY (from RugCheck.xyz):
   Security Score: {all_data.get('security_score', 'N/A')}/100
   Mint Authority: {'❌ ACTIVE - CAN MINT!' if all_data.get('has_mint', False) else '✅ Revoked'}
   Freeze Authority: {'❌ ACTIVE - CAN FREEZE!' if all_data.get('has_freeze', False) else '✅ Revoked'}
   LP Locked: {all_data.get('lp_locked_pct', 0):.1f}%
   Risks Found: {all_data.get('risk_count', 0)} ({all_data.get('danger_count', 0)} danger, {all_data.get('warn_count', 0)} warning)
   Risk Details: {all_data.get('risk_details', 'None')}
   
👥 HOLDER DISTRIBUTION:
   Total Holders: {all_data.get('holder_count', 0):,}
   Top Holder: {all_data.get('top_holder_percent', 0):.1f}%
   Top 10 Holders: {all_data.get('top_10_percent', 0):.1f}%
   Concentration Risk: {'HIGH' if all_data.get('top_holder_percent', 0) > 20 else 'MEDIUM' if all_data.get('top_holder_percent', 0) > 10 else 'LOW'}
   
⏰ TOKEN AGE:
   Age: {all_data.get('age_hours', 999):.1f} hours
   
✅ VERIFICATION:
   On Jupiter: {all_data.get('on_jupiter', 'Unknown')}
   Source: {all_data.get('source', 'Unknown')}
"""

        # ──────────────────────────────────────────────────────────────────
        # INJECT TECHNICAL ANALYSIS (from Aarna MCP) if available
        # ──────────────────────────────────────────────────────────────────
        if all_data.get("ta_signal"):
            prompt += f"""

📊 TECHNICAL ANALYSIS (from MCP Signal Provider):
   Composite Signal: {all_data.get('ta_signal', 'N/A').upper()}
   Signal Confidence: {all_data.get('ta_confidence', 0):.0%}
   Price: ${all_data.get('ta_price', 0):,.2f}
   Bullish Signals: {all_data.get('ta_bullish_count', 0)} | Bearish: {all_data.get('ta_bearish_count', 0)}
   RSI: {all_data.get('ta_rsi', 'N/A')}
   Summary: {all_data.get('ta_signal_summary', 'N/A')}
   Indicators: {all_data.get('ta_indicators_summary', 'N/A')}
"""

        prompt += f"""
═══════════════════════════════════════════════════════════════
                    YOUR ANALYSIS
═══════════════════════════════════════════════════════════════

Consider:
1. Is there strong buying momentum? (buy/sell ratio, volume trends)
2. Are security checks passed? (no mint/freeze auth, good score)
3. Is holder distribution healthy? (not too concentrated)
4. Is the risk/reward favorable?
5. Is this a potential rug pull?
6. If TA signals available: does the composite signal confirm momentum? Is trend bullish? Is RSI overbought (>70 caution) or healthy?

Return ONLY valid JSON:
{{"decision":"BUY or SKIP","confidence":0-100,"token_score":0-100,"sentiment_score":0-100,"risk_score":0-100,"reasoning":"1-2 sentences explaining your decision"}}"""

        system = """You are a DEGEN Solana memecoin trader AI in SIMULATION/TEST MODE. You hunt for 10x-100x opportunities.

⚠️ SIMULATION MODE ACTIVE - BE MORE AGGRESSIVE! ⚠️
This is paper trading - we WANT to test trades!

MEMECOIN REALITY:
- Memecoins are HIGH RISK, HIGH REWARD
- Early entry = biggest gains (first 1-24 hours)
- Volume surge = momentum = potential moon
- Buy/Sell ratio > 1.2 = buying pressure
- LP unlocked is NORMAL for new Pump.fun tokens!

BUY SIGNALS (any 2+ = BUY):
✅ Volume > $50k in 24h (shows interest)
✅ Strong price momentum (+10%+ recently)
✅ No mint authority (can't print more tokens)
✅ No freeze authority (can't freeze wallets)
✅ Buy pressure > sell pressure
✅ Token age 1-48 hours (early = good for gains)
✅ TA composite signal = BULLISH with confidence > 60%
✅ TA trend regime = uptrend + momentum accelerating

HARD SKIP (only these = SKIP):
❌ Mint authority ACTIVE (can print = definite rug)
❌ Freeze authority ACTIVE (can freeze wallets)
❌ Volume < $10k (dead/no interest)
❌ Top holder > 50% (extreme whale)
❌ TA signal = BEARISH with high confidence + downtrend regime

IMPORTANT: LP unlocked is NORMAL for Pump.fun tokens. Don't skip just for this!
In SIMULATION MODE, be willing to take calculated risks to test the system.

Return valid JSON only, no markdown."""
        
        result = await self._call_agent(system, prompt)
        
        if not result:
            return None
        
        decision_str = result.get("decision", "SKIP")
        try:
            decision = Decision[decision_str.upper().replace(" ", "")]
        except KeyError:
            decision = Decision.SKIP
        
        token_score = result.get("token_score", 50)
        sentiment_score = result.get("sentiment_score", 50)
        risk_score = result.get("risk_score", 50)
        confidence = result.get("confidence", 0)
        reasoning = result.get("reasoning", "No reason given")
        
        logger.info(f"   Scores: T={token_score} S={sentiment_score} R={risk_score}")
        logger.info(f"   Decision: {decision.value} ({confidence}%)")
        logger.info(f"   🧠 Reason: {reasoning}")
        
        return TradingDecision(
            decision=decision,
            confidence=confidence,
            entry_price=all_data.get("price"),
            stop_loss=None,
            take_profit=None,
            position_size_percent=5 if decision == Decision.BUY else 0,
            reasoning=result.get("reasoning", ""),
            token_score=token_score,
            sentiment_score=sentiment_score,
            risk_score=risk_score
        )


# Test
if __name__ == "__main__":
    async def _run_demo():
        engine = AIEngine()

        test_data = {
            "symbol": "TESTMEME",
            "name": "Test Meme Coin",
            "price": 0.00001234,
            "liquidity": 75000,
            "volume_24h": 150000,
            "market_cap": 500000,
            "holder_count": 1500,
            "age_hours": 12,
            "top_10_percent": 35,
            "top_holder_percent": 8,
            "has_freeze": False,
            "has_mint": False,
            "verified": True,
            "liquidity_locked": True,
            "has_website": True,
            "has_twitter": True,
            "twitter_mentions": 250,
            "telegram_members": 800,
            "price_change_1h": 15,
            "price_change_24h": 85,
            "volume_spike": True,
            "notable_buys": ["whale1.sol bought $5k"]
        }

        decision = await engine.full_analysis(test_data)

        if decision:
            print(f"\n{'='*50}")
            print(f"Final Decision: {decision.decision.value}")
            print(f"Confidence: {decision.confidence}%")
            print(f"Position Size: {decision.position_size_percent}%")
            if decision.entry_price:
                print(f"Entry: ${decision.entry_price:.8f}")
            if decision.stop_loss:
                print(f"Stop Loss: ${decision.stop_loss:.8f}")
            if decision.take_profit:
                print(f"Take Profit: ${decision.take_profit:.8f}")
            print(f"\nReasoning: {decision.reasoning}")

    asyncio.run(_run_demo())
