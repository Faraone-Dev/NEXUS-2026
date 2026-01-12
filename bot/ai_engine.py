"""
NEXUS AI Trading Bot - AI Engine
=================================
DeepSeek integration for market analysis
"""

import json
from openai import OpenAI
from loguru import logger
from config import config


class AIEngine:
    """AI Engine using DeepSeek for market analysis"""
    
    SYSTEM_PROMPT = """You are NEXUS, an elite AI trading analyst. You analyze crypto markets with precision.

RULES:
1. Always respond with valid JSON only
2. Be decisive - no "maybe" or "uncertain"
3. Base decisions on DATA, not emotions
4. Consider: price action, volume, funding, sentiment, news
5. Risk management is priority

RESPONSE FORMAT (JSON only):
{
    "decision": "LONG" | "SHORT" | "WAIT",
    "confidence": 1-100,
    "reasoning": "Brief explanation max 50 words",
    "entry_price": null or number,
    "stop_loss": null or number,
    "take_profit": null or number,
    "risk_level": "LOW" | "MEDIUM" | "HIGH"
}"""

    def __init__(self):
        self.client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL
        )
        self.model = "deepseek-chat"
        logger.info("AI Engine initialized with DeepSeek")
    
    def analyze(self, market_data: dict) -> dict:
        """
        Analyze market data and return trading decision
        
        Args:
            market_data: Dict containing price, volume, indicators, news, etc.
            
        Returns:
            Dict with decision, confidence, reasoning, entry/exit levels
        """
        
        # Build analysis prompt
        prompt = self._build_prompt(market_data)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower = more consistent
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content
            
            # Parse JSON response
            result = self._parse_response(result_text)
            
            logger.info(f"AI Decision: {result['decision']} (Confidence: {result['confidence']}%)")
            
            return result
            
        except Exception as e:
            logger.error(f"AI Engine error: {e}")
            return {
                "decision": "WAIT",
                "confidence": 0,
                "reasoning": f"Error: {str(e)}",
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "risk_level": "HIGH"
            }
    
    def _build_prompt(self, market_data: dict) -> str:
        """Build analysis prompt from market data"""
        
        prompt = f"""ANALYZE THIS MARKET DATA FOR {config.TRADING_SYMBOL}:

=== PRICE DATA ===
Current Price: ${market_data.get('price', 'N/A')}
24h Change: {market_data.get('change_24h', 'N/A')}%
24h High: ${market_data.get('high_24h', 'N/A')}
24h Low: ${market_data.get('low_24h', 'N/A')}
24h Volume: ${market_data.get('volume_24h', 'N/A')}

=== MARKET STRUCTURE ===
Funding Rate: {market_data.get('funding_rate', 'N/A')}%
Open Interest: ${market_data.get('open_interest', 'N/A')}
OI Change 1h: {market_data.get('oi_change_1h', 'N/A')}%
Long/Short Ratio: {market_data.get('long_short_ratio', 'N/A')}

=== LIQUIDATIONS ===
Long Liquidations 24h: ${market_data.get('long_liquidations', 'N/A')}
Short Liquidations 24h: ${market_data.get('short_liquidations', 'N/A')}
Nearest Long Liq Level: ${market_data.get('nearest_long_liq', 'N/A')}
Nearest Short Liq Level: ${market_data.get('nearest_short_liq', 'N/A')}

=== SENTIMENT ===
Fear & Greed Index: {market_data.get('fear_greed', 'N/A')}
Social Volume: {market_data.get('social_volume', 'N/A')}
News Sentiment: {market_data.get('news_sentiment', 'N/A')}

=== RECENT NEWS ===
{market_data.get('news', 'No recent news')}

=== TECHNICAL ===
RSI (14): {market_data.get('rsi', 'N/A')}
MACD Signal: {market_data.get('macd_signal', 'N/A')}
EMA 20 vs Price: {market_data.get('ema_20_position', 'N/A')}
EMA 50 vs Price: {market_data.get('ema_50_position', 'N/A')}

Based on this data, what is your trading decision? Consider:
1. Is there a clear trend or reversal setup?
2. Is funding/positioning extreme (potential squeeze)?
3. Any major liquidation levels nearby?
4. Does sentiment support or contradict price?
5. Risk/reward ratio?

Respond with JSON only."""
        
        return prompt
    
    def _parse_response(self, response_text: str) -> dict:
        """Parse AI response to dict"""
        
        # Try to find JSON in response
        try:
            # Remove markdown code blocks if present
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            return json.loads(text)
            
        except json.JSONDecodeError:
            # Fallback: try to extract key info
            logger.warning("Failed to parse AI JSON, using fallback")
            
            decision = "WAIT"
            if "LONG" in response_text.upper():
                decision = "LONG"
            elif "SHORT" in response_text.upper():
                decision = "SHORT"
            
            return {
                "decision": decision,
                "confidence": 50,
                "reasoning": response_text[:200],
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "risk_level": "MEDIUM"
            }


# Test if run directly
if __name__ == "__main__":
    engine = AIEngine()
    
    # Test with sample data
    test_data = {
        "price": 97500,
        "change_24h": -1.2,
        "high_24h": 98500,
        "low_24h": 96800,
        "volume_24h": "2.3B",
        "funding_rate": 0.01,
        "open_interest": "18.5B",
        "oi_change_1h": 2.1,
        "long_short_ratio": 1.8,
        "long_liquidations": "45M",
        "short_liquidations": "12M",
        "nearest_long_liq": 95000,
        "nearest_short_liq": 99500,
        "fear_greed": 72,
        "news_sentiment": "Bullish",
        "news": "Bitcoin ETF sees $200M inflows",
        "rsi": 58,
        "macd_signal": "Bullish crossover",
        "ema_20_position": "Price above",
        "ema_50_position": "Price above"
    }
    
    result = engine.analyze(test_data)
    print(json.dumps(result, indent=2))
