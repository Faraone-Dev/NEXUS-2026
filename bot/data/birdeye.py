"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Birdeye Client                            ║
║                  Token analytics, holders, and market data                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import httpx
from loguru import logger
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from config import config


@dataclass
class TokenOverview:
    """Complete token overview"""
    mint: str
    symbol: str
    name: str
    price: float
    price_change_24h: float
    volume_24h: float
    liquidity: float
    market_cap: float
    holder_count: int
    created_at: Optional[datetime] = None


@dataclass
class TokenSecurity:
    """Token security analysis"""
    mint: str
    is_verified: bool
    has_freeze_authority: bool
    has_mint_authority: bool
    top_10_holders_percent: float
    creator_balance_percent: float


@dataclass
class TradeInfo:
    """Recent trade information"""
    buys_24h: int
    sells_24h: int
    buy_volume_24h: float
    sell_volume_24h: float
    unique_wallets_24h: int


class BirdeyeClient:
    """
    Birdeye API Client
    
    Best for:
    - Token analytics
    - Holder data
    - Historical prices
    - New token discovery
    """
    
    BASE_URL = "https://public-api.birdeye.so"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.BIRDEYE_API_KEY
        self.headers = {
            "X-API-KEY": self.api_key,
            "x-chain": "solana"
        }
        self.client = httpx.AsyncClient(timeout=5, headers=self.headers)
        logger.info("Birdeye client initialized")
    
    async def get_token_overview(self, mint: str) -> Optional[TokenOverview]:
        """
        Get complete token overview
        
        Args:
            mint: Token mint address
            
        Returns:
            TokenOverview or None
        """
        try:
            url = f"{self.BASE_URL}/defi/token_overview"
            params = {"address": mint}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("success"):
                return None
                
            d = data["data"]
            
            return TokenOverview(
                mint=mint,
                symbol=d.get("symbol", "???"),
                name=d.get("name", "Unknown"),
                price=float(d.get("price", 0)),
                price_change_24h=float(d.get("priceChange24hPercent", 0)),
                volume_24h=float(d.get("v24hUSD", 0)),
                liquidity=float(d.get("liquidity", 0)),
                market_cap=float(d.get("mc", 0)),
                holder_count=int(d.get("holder", 0)),
                created_at=None  # Parse if needed
            )
            
        except Exception as e:
            logger.error(f"Birdeye overview error: {e}")
            return None
    
    async def get_token_security(self, mint: str) -> Optional[TokenSecurity]:
        """
        Get token security analysis
        
        Args:
            mint: Token mint address
            
        Returns:
            TokenSecurity or None
        """
        try:
            url = f"{self.BASE_URL}/defi/token_security"
            params = {"address": mint}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("success"):
                return None
                
            d = data["data"]
            
            return TokenSecurity(
                mint=mint,
                is_verified=d.get("isVerified", False),
                has_freeze_authority=d.get("freezeAuthority") is not None,
                has_mint_authority=d.get("mintAuthority") is not None,
                top_10_holders_percent=float(d.get("top10HolderPercent", 0)),
                creator_balance_percent=float(d.get("creatorPercentage", 0))
            )
            
        except Exception as e:
            logger.error(f"Birdeye security error: {e}")
            return None
    
    async def get_trade_info(self, mint: str) -> Optional[TradeInfo]:
        """
        Get 24h trading activity
        
        Args:
            mint: Token mint address
            
        Returns:
            TradeInfo or None
        """
        try:
            url = f"{self.BASE_URL}/defi/v3/token/trade-data/single"
            params = {"address": mint}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("success"):
                return None
                
            d = data["data"]
            
            return TradeInfo(
                buys_24h=int(d.get("buy24h", 0)),
                sells_24h=int(d.get("sell24h", 0)),
                buy_volume_24h=float(d.get("vBuy24hUSD", 0)),
                sell_volume_24h=float(d.get("vSell24hUSD", 0)),
                unique_wallets_24h=int(d.get("uniqueWallet24h", 0))
            )
            
        except Exception as e:
            logger.error(f"Birdeye trade info error: {e}")
            return None
    
    async def get_new_listings(self, limit: int = 50) -> list[dict]:
        """
        Get newly listed tokens (uses trending as fallback)
        
        Args:
            limit: Number of tokens to fetch
            
        Returns:
            List of new token data
        """
        try:
            # Try new_listing first
            url = f"{self.BASE_URL}/defi/v2/tokens/new_listing"
            params = {"limit": limit}
            
            response = await self.client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("data", {}).get("items", [])
            
            # Fallback: use trending tokens (more reliable)
            logger.debug("Using trending tokens as fallback")
            url = f"{self.BASE_URL}/defi/tokenlist"
            params = {
                "sort_by": "v24hUSD",  # Sort by 24h volume
                "sort_type": "desc",
                "offset": 0,
                "limit": limit
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("success"):
                return []
            
            # Transform to expected format
            tokens = data.get("data", {}).get("tokens", [])
            return [
                {
                    "address": t.get("address"),
                    "symbol": t.get("symbol"),
                    "name": t.get("name"),
                    "price": t.get("v24hUSD", 0),
                    "liquidity": t.get("liquidity", 0),
                    "volume24h": t.get("v24hUSD", 0)
                }
                for t in tokens
            ]
            
        except Exception as e:
            logger.error(f"Birdeye token list error: {e}")
            return []
    
    async def get_trending(self, limit: int = 20) -> list[dict]:
        """
        Get trending tokens
        
        Args:
            limit: Number of tokens
            
        Returns:
            List of trending tokens
        """
        try:
            url = f"{self.BASE_URL}/defi/v2/tokens/trending"
            params = {"limit": limit}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("success"):
                return []
                
            return data.get("data", {}).get("items", [])
            
        except Exception as e:
            logger.error(f"Birdeye trending error: {e}")
            return []
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = BirdeyeClient()
        
        # Test with BONK token
        bonk = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        
        overview = await client.get_token_overview(bonk)
        if overview:
            print(f"\n{overview.name} ({overview.symbol})")
            print(f"  Price: ${overview.price:.8f}")
            print(f"  24h Change: {overview.price_change_24h:.2f}%")
            print(f"  Volume: ${overview.volume_24h:,.0f}")
            print(f"  Liquidity: ${overview.liquidity:,.0f}")
            print(f"  Holders: {overview.holder_count:,}")
        
        security = await client.get_token_security(bonk)
        if security:
            print(f"\nSecurity:")
            print(f"  Verified: {security.is_verified}")
            print(f"  Freeze Auth: {security.has_freeze_authority}")
            print(f"  Mint Auth: {security.has_mint_authority}")
            print(f"  Top 10 Holders: {security.top_10_holders_percent:.2f}%")
        
        await client.close()
    
    asyncio.run(test())
