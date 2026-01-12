"""
NEXUS AI Trading Bot - Configuration
=====================================
Loads all settings from environment variables
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

class Config:
    """Central configuration class"""
    
    # ============ AI PROVIDER ============
    DEEPSEEK_API_KEY: str = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL: str = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    
    # ============ EXCHANGE ============
    BINANCE_API_KEY: str = os.getenv('BINANCE_API_KEY', '')
    BINANCE_SECRET_KEY: str = os.getenv('BINANCE_SECRET_KEY', '')
    BINANCE_TESTNET: bool = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'
    
    # ============ TRADING CONFIG ============
    TRADING_SYMBOL: str = os.getenv('TRADING_SYMBOL', 'BTC/USDT')
    TRADING_LEVERAGE: int = int(os.getenv('TRADING_LEVERAGE', '5'))
    POSITION_SIZE_PERCENT: float = float(os.getenv('POSITION_SIZE_PERCENT', '10'))
    MAX_POSITIONS: int = int(os.getenv('MAX_POSITIONS', '3'))
    STOP_LOSS_PERCENT: float = float(os.getenv('STOP_LOSS_PERCENT', '2'))
    TAKE_PROFIT_PERCENT: float = float(os.getenv('TAKE_PROFIT_PERCENT', '5'))
    
    # ============ BOT SETTINGS ============
    ANALYSIS_INTERVAL: int = int(os.getenv('ANALYSIS_INTERVAL_SECONDS', '300'))
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    DRY_RUN: bool = os.getenv('DRY_RUN', 'true').lower() == 'true'
    
    # ============ DATA SOURCES ============
    COINGLASS_API_KEY: str = os.getenv('COINGLASS_API_KEY', '')
    CRYPTOPANIC_API_KEY: str = os.getenv('CRYPTOPANIC_API_KEY', '')
    
    # ============ TELEGRAM ============
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')
    
    @classmethod
    def validate(cls) -> list:
        """Validate required config values"""
        errors = []
        
        if not cls.DEEPSEEK_API_KEY:
            errors.append("DEEPSEEK_API_KEY is required")
        
        if not cls.BINANCE_API_KEY:
            errors.append("BINANCE_API_KEY is required")
            
        if not cls.BINANCE_SECRET_KEY:
            errors.append("BINANCE_SECRET_KEY is required")
            
        return errors
    
    @classmethod
    def print_config(cls):
        """Print current config (hiding secrets)"""
        print("\n" + "="*50)
        print("NEXUS AI BOT - CONFIGURATION")
        print("="*50)
        print(f"AI Provider: DeepSeek")
        print(f"API Key: {'*' * 20}{cls.DEEPSEEK_API_KEY[-4:] if cls.DEEPSEEK_API_KEY else 'NOT SET'}")
        print(f"Exchange: Binance {'TESTNET' if cls.BINANCE_TESTNET else 'LIVE'}")
        print(f"Symbol: {cls.TRADING_SYMBOL}")
        print(f"Leverage: {cls.TRADING_LEVERAGE}x")
        print(f"Position Size: {cls.POSITION_SIZE_PERCENT}%")
        print(f"Stop Loss: {cls.STOP_LOSS_PERCENT}%")
        print(f"Take Profit: {cls.TAKE_PROFIT_PERCENT}%")
        print(f"Analysis Interval: {cls.ANALYSIS_INTERVAL}s")
        print(f"Dry Run: {cls.DRY_RUN}")
        print("="*50 + "\n")


# Global config instance
config = Config()
