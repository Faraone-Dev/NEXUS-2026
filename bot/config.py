"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - SOLANA EDITION                            ║
║                              Configuration                                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional

# Load .env
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')


@dataclass
class Config:
    """Central configuration - all settings from .env"""
    
    # ═══════════════════════════════════════════════════════════════════════
    #                              AI PROVIDER
    # ═══════════════════════════════════════════════════════════════════════
    DEEPSEEK_API_KEY: str = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL: str = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    
    # ═══════════════════════════════════════════════════════════════════════
    #                         SOLANA RPC & ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════════
    SOLANA_RPC_URL: str = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
    SOLANA_WS_URL: str = os.getenv('SOLANA_WS_URL', 'wss://api.mainnet-beta.solana.com')
    
    # Helius (premium RPC)
    HELIUS_API_KEY: str = os.getenv('HELIUS_API_KEY', '')
    HELIUS_RPC_URL: str = os.getenv('HELIUS_RPC_URL', 'https://mainnet.helius-rpc.com')
    
    # ═══════════════════════════════════════════════════════════════════════
    #                         DATA APIs & ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════════
    # Jupiter (V3 API - requires key from portal.jup.ag)
    JUPITER_API_KEY: str = os.getenv('JUPITER_API_KEY', '')
    JUPITER_BASE_URL: str = os.getenv('JUPITER_BASE_URL', 'https://api.jup.ag')
    JUPITER_PRICE_API: str = os.getenv('JUPITER_PRICE_API', 'https://api.jup.ag/price/v3')
    JUPITER_QUOTE_API: str = os.getenv('JUPITER_QUOTE_API', 'https://api.jup.ag/swap/v1/quote')
    JUPITER_SWAP_API: str = os.getenv('JUPITER_SWAP_API', 'https://api.jup.ag/swap/v1/swap')
    
    # Birdeye
    BIRDEYE_API_KEY: str = os.getenv('BIRDEYE_API_KEY', '')
    BIRDEYE_API_URL: str = os.getenv('BIRDEYE_API_URL', 'https://public-api.birdeye.so')
    
    # DexScreener
    DEXSCREENER_API_URL: str = os.getenv('DEXSCREENER_API_URL', 'https://api.dexscreener.com/latest')
    
    # Solscan
    SOLSCAN_API_URL: str = os.getenv('SOLSCAN_API_URL', 'https://api.solscan.io')
    SOLSCAN_API_KEY: str = os.getenv('SOLSCAN_API_KEY', '')
    
    # ═══════════════════════════════════════════════════════════════════════
    #                              WALLET
    # ═══════════════════════════════════════════════════════════════════════
    SOLANA_PRIVATE_KEY: str = os.getenv('SOLANA_PRIVATE_KEY', '')
    SOLANA_WALLET_ADDRESS: str = os.getenv('SOLANA_WALLET_ADDRESS', '')
    
    # ═══════════════════════════════════════════════════════════════════════
    #                              TELEGRAM
    # ═══════════════════════════════════════════════════════════════════════
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # ═══════════════════════════════════════════════════════════════════════
    #                           TRADING CONFIG
    # ═══════════════════════════════════════════════════════════════════════
    POSITION_SIZE_PERCENT: float = float(os.getenv('POSITION_SIZE_PERCENT', '10'))  # 10% per trade
    MAX_POSITIONS: int = int(os.getenv('MAX_POSITIONS', '1'))  # ONE at a time - focus mode
    STOP_LOSS_PERCENT: float = float(os.getenv('STOP_LOSS_PERCENT', '15'))
    TAKE_PROFIT_PERCENT: float = float(os.getenv('TAKE_PROFIT_PERCENT', '50'))
    
    # ═══════════════════════════════════════════════════════════════════════
    #                              FILTERS
    # ═══════════════════════════════════════════════════════════════════════
    MIN_LIQUIDITY_USD: float = float(os.getenv('MIN_LIQUIDITY_USD', '50000'))
    MIN_AI_SCORE: int = int(os.getenv('MIN_AI_SCORE', '70'))
    MIN_CONFIDENCE: int = int(os.getenv('MIN_CONFIDENCE', '75'))
    MAX_TOKEN_AGE_HOURS: int = int(os.getenv('MAX_TOKEN_AGE_HOURS', '24'))
    
    # ═══════════════════════════════════════════════════════════════════════
    #                           BOT SETTINGS
    # ═══════════════════════════════════════════════════════════════════════
    SCAN_INTERVAL: int = int(os.getenv('SCAN_INTERVAL_SECONDS', '15'))  # 15s for active monitoring
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    DRY_RUN: bool = os.getenv('DRY_RUN', 'true').lower() == 'true'
    
    # Simulation Mode - Paper trading con dati REALI
    SIMULATION_MODE: bool = os.getenv('SIMULATION_MODE', 'true').lower() == 'true'
    SIMULATION_STARTING_SOL: float = float(os.getenv('SIMULATION_STARTING_SOL', '1.0'))
    
    # ═══════════════════════════════════════════════════════════════════════
    #                         AARNA MCP (TA SIGNALS)
    # ═══════════════════════════════════════════════════════════════════════
    AARNA_API_KEY: str = os.getenv('AARNA_API_KEY', '')  # Smithery API key
    AARNA_NAMESPACE: str = os.getenv('AARNA_NAMESPACE', 'gopher-LzOh')
    AARNA_CONNECTION: str = os.getenv('AARNA_CONNECTION', 'aarnaai-atars-mcp')
    AARNA_ENABLED: bool = os.getenv('AARNA_ENABLED', 'true').lower() == 'true'
    
    # ═══════════════════════════════════════════════════════════════════════
    #                              SOCIAL
    # ═══════════════════════════════════════════════════════════════════════
    TWITTER_BEARER_TOKEN: str = os.getenv('TWITTER_BEARER_TOKEN', '')
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration"""
        errors = []
        
        if not cls.DEEPSEEK_API_KEY:
            errors.append("❌ DEEPSEEK_API_KEY is required")
        
        if not cls.HELIUS_API_KEY:
            errors.append("⚠️ HELIUS_API_KEY recommended for best performance")
        
        if not cls.BIRDEYE_API_KEY:
            errors.append("⚠️ BIRDEYE_API_KEY recommended for token data")
            
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("⚠️ TELEGRAM_BOT_TOKEN not set - no alerts")
            
        if not cls.SOLANA_PRIVATE_KEY and not cls.DRY_RUN:
            errors.append("❌ SOLANA_PRIVATE_KEY required for live trading")
            
        return errors
    
    @classmethod
    def print_config(cls):
        """Print current configuration (hiding secrets)"""
        
        def mask(s: str) -> str:
            if not s:
                return "❌ NOT SET"
            return f"✅ ***{s[-4:]}"
        
        print("\n" + "═" * 60)
        print("           🚀 NEXUS AI - SOLANA EDITION 🚀")
        print("═" * 60)
        print(f"  DeepSeek API:    {mask(cls.DEEPSEEK_API_KEY)}")
        print(f"  Helius API:      {mask(cls.HELIUS_API_KEY)}")
        print(f"  Birdeye API:     {mask(cls.BIRDEYE_API_KEY)}")
        print(f"  Telegram:        {mask(cls.TELEGRAM_BOT_TOKEN)}")
        print(f"  Wallet:          {mask(cls.SOLANA_WALLET_ADDRESS)}")
        print("─" * 60)
        print(f"  Position Size:   {cls.POSITION_SIZE_PERCENT}%")
        print(f"  Max Positions:   {cls.MAX_POSITIONS}")
        print(f"  Stop Loss:       {cls.STOP_LOSS_PERCENT}%")
        print(f"  Take Profit:     {cls.TAKE_PROFIT_PERCENT}%")
        print("─" * 60)
        print(f"  Min Liquidity:   ${cls.MIN_LIQUIDITY_USD:,.0f}")
        print(f"  Min AI Score:    {cls.MIN_AI_SCORE}")
        print(f"  Min Confidence:  {cls.MIN_CONFIDENCE}%")
        print(f"  Max Token Age:   {cls.MAX_TOKEN_AGE_HOURS}h")
        print("─" * 60)
        print(f"  Scan Interval:   {cls.SCAN_INTERVAL}s")
        print(f"  Dry Run:         {'🟡 YES' if cls.DRY_RUN else '🔴 NO - LIVE'}")
        print("═" * 60 + "\n")


# Global instance
config = Config()


if __name__ == "__main__":
    Config.print_config()
    errors = Config.validate()
    if errors:
        print("\nConfiguration Issues:")
        for e in errors:
            print(f"  {e}")
