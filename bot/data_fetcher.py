"""
NEXUS AI Trading Bot - Data Fetcher
====================================
Aggregates data from multiple sources
"""

import requests
from loguru import logger
from config import config
from exchange import Exchange
from typing import Optional, Dict
import ta
import pandas as pd


class DataFetcher:
    """Fetches and aggregates market data from multiple sources"""
    
    def __init__(self, exchange: Exchange):
        self.exchange = exchange
        self.coinglass_base = "https://open-api.coinglass.com/public/v2"
        self.cryptopanic_base = "https://cryptopanic.com/api/v1"
        self.alternative_me = "https://api.alternative.me"
        
    def get_all_data(self) -> dict:
        """Aggregate all data sources into one dict"""
        
        data = {}
        
        # Exchange data (always available)
        data.update(self._get_exchange_data())
        
        # Technical indicators
        data.update(self._get_technical_indicators())
        
        # Funding & OI (Coinglass or exchange)
        data.update(self._get_derivatives_data())
        
        # Fear & Greed
        data.update(self._get_sentiment_data())
        
        # News
        data.update(self._get_news_data())
        
        return data
    
    def _get_exchange_data(self) -> dict:
        """Get data from exchange"""
        ticker = self.exchange.get_ticker()
        
        return {
            'price': ticker.get('price', 0),
            'bid': ticker.get('bid', 0),
            'ask': ticker.get('ask', 0),
            'high_24h': ticker.get('high_24h', 0),
            'low_24h': ticker.get('low_24h', 0),
            'volume_24h': self._format_number(ticker.get('volume_24h', 0)),
            'change_24h': round(ticker.get('change_24h', 0), 2)
        }
    
    def _get_technical_indicators(self) -> dict:
        """Calculate technical indicators from OHLCV"""
        try:
            ohlcv = self.exchange.get_ohlcv('1h', 100)
            
            if not ohlcv:
                return {}
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # RSI
            rsi = ta.momentum.RSIIndicator(df['close'], window=14)
            current_rsi = round(rsi.rsi().iloc[-1], 1)
            
            # MACD
            macd = ta.trend.MACD(df['close'])
            macd_line = macd.macd().iloc[-1]
            signal_line = macd.macd_signal().iloc[-1]
            macd_signal = "Bullish crossover" if macd_line > signal_line else "Bearish crossover"
            
            # EMAs
            ema20 = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator().iloc[-1]
            ema50 = ta.trend.EMAIndicator(df['close'], window=50).ema_indicator().iloc[-1]
            current_price = df['close'].iloc[-1]
            
            ema_20_position = "Price above" if current_price > ema20 else "Price below"
            ema_50_position = "Price above" if current_price > ema50 else "Price below"
            
            return {
                'rsi': current_rsi,
                'macd_signal': macd_signal,
                'ema_20_position': ema_20_position,
                'ema_50_position': ema_50_position
            }
            
        except Exception as e:
            logger.warning(f"Error calculating indicators: {e}")
            return {
                'rsi': 'N/A',
                'macd_signal': 'N/A',
                'ema_20_position': 'N/A',
                'ema_50_position': 'N/A'
            }
    
    def _get_derivatives_data(self) -> dict:
        """Get funding rate, OI, liquidations from Coinglass or exchange"""
        
        # Try exchange first (always available)
        funding = self.exchange.get_funding_rate()
        
        data = {
            'funding_rate': round(funding, 4) if funding else 'N/A',
            'open_interest': 'N/A',
            'oi_change_1h': 'N/A',
            'long_short_ratio': 'N/A',
            'long_liquidations': 'N/A',
            'short_liquidations': 'N/A',
            'nearest_long_liq': 'N/A',
            'nearest_short_liq': 'N/A'
        }
        
        # Try Coinglass for more data
        if config.COINGLASS_API_KEY:
            try:
                headers = {'coinglassSecret': config.COINGLASS_API_KEY}
                
                # Open Interest
                oi_resp = requests.get(
                    f"{self.coinglass_base}/open_interest",
                    headers=headers,
                    params={'symbol': 'BTC'},
                    timeout=5
                )
                if oi_resp.status_code == 200:
                    oi_data = oi_resp.json().get('data', {})
                    data['open_interest'] = self._format_number(oi_data.get('openInterest', 0))
                
                # Long/Short Ratio
                ls_resp = requests.get(
                    f"{self.coinglass_base}/long_short",
                    headers=headers,
                    params={'symbol': 'BTC', 'interval': '1h'},
                    timeout=5
                )
                if ls_resp.status_code == 200:
                    ls_data = ls_resp.json().get('data', [])
                    if ls_data:
                        data['long_short_ratio'] = round(ls_data[-1].get('longRate', 50) / max(ls_data[-1].get('shortRate', 50), 1), 2)
                
            except Exception as e:
                logger.debug(f"Coinglass API error: {e}")
        
        return data
    
    def _get_sentiment_data(self) -> dict:
        """Get Fear & Greed Index"""
        try:
            resp = requests.get(f"{self.alternative_me}/fng/", timeout=5)
            if resp.status_code == 200:
                data = resp.json().get('data', [{}])[0]
                return {
                    'fear_greed': int(data.get('value', 50)),
                    'fear_greed_label': data.get('value_classification', 'Neutral')
                }
        except Exception as e:
            logger.debug(f"Fear & Greed API error: {e}")
        
        return {
            'fear_greed': 50,
            'fear_greed_label': 'Neutral'
        }
    
    def _get_news_data(self) -> dict:
        """Get latest crypto news"""
        news_items = []
        
        if config.CRYPTOPANIC_API_KEY:
            try:
                resp = requests.get(
                    f"{self.cryptopanic_base}/posts/",
                    params={
                        'auth_token': config.CRYPTOPANIC_API_KEY,
                        'currencies': 'BTC',
                        'kind': 'news',
                        'filter': 'important'
                    },
                    timeout=5
                )
                if resp.status_code == 200:
                    results = resp.json().get('results', [])[:5]
                    for item in results:
                        sentiment = "Neutral"
                        votes = item.get('votes', {})
                        if votes.get('positive', 0) > votes.get('negative', 0):
                            sentiment = "Bullish"
                        elif votes.get('negative', 0) > votes.get('positive', 0):
                            sentiment = "Bearish"
                        
                        news_items.append(f"[{sentiment}] {item.get('title', '')}")
                        
            except Exception as e:
                logger.debug(f"CryptoPanic API error: {e}")
        
        news_text = "\n".join(news_items) if news_items else "No recent news available"
        
        # Overall news sentiment
        bullish_count = sum(1 for n in news_items if 'Bullish' in n)
        bearish_count = sum(1 for n in news_items if 'Bearish' in n)
        
        if bullish_count > bearish_count:
            news_sentiment = "Bullish"
        elif bearish_count > bullish_count:
            news_sentiment = "Bearish"
        else:
            news_sentiment = "Neutral"
        
        return {
            'news': news_text,
            'news_sentiment': news_sentiment,
            'social_volume': 'N/A'
        }
    
    def _format_number(self, num) -> str:
        """Format large numbers (1B, 1M, etc)"""
        try:
            num = float(num)
            if num >= 1_000_000_000:
                return f"{num/1_000_000_000:.1f}B"
            elif num >= 1_000_000:
                return f"{num/1_000_000:.1f}M"
            elif num >= 1_000:
                return f"{num/1_000:.1f}K"
            else:
                return str(round(num, 2))
        except:
            return str(num)


# Test if run directly
if __name__ == "__main__":
    from exchange import Exchange
    
    exchange = Exchange()
    fetcher = DataFetcher(exchange)
    
    data = fetcher.get_all_data()
    
    print("\n=== AGGREGATED MARKET DATA ===")
    for key, value in data.items():
        print(f"{key}: {value}")
