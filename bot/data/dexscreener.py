"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        NEXUS AI - DexScreener Client                          ║
║                       Token pairs and real-time data                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import httpx
from loguru import logger
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TokenPair:
    """DEX trading pair data"""
    pair_address: str
    base_token: str
    base_symbol: str
    quote_token: str
    quote_symbol: str
    price_usd: float
    price_native: float
    price_change_5m: float
    price_change_1h: float
    price_change_6h: float
    price_change_24h: float
    volume_24h: float
    liquidity_usd: float
    fdv: float
    pair_created_at: Optional[datetime]
    dex_id: str
    url: str
    
    @property
    def age_hours(self) -> float:
        """Get pair age in hours"""
        if not self.pair_created_at:
            return 999999
        delta = datetime.now() - self.pair_created_at
        return delta.total_seconds() / 3600


class DexScreenerClient:
    """
    DexScreener API Client
    
    Best for:
    - Real-time pair data
    - Multi-DEX coverage
    - Price charts
    - New pairs discovery
    
    Note: Free API, no key required
    """
    
    BASE_URL = "https://api.dexscreener.com"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=5)
        logger.info("DexScreener client initialized")
    
    async def get_token_pairs(self, mint: str) -> list[TokenPair]:
        """
        Get all pairs for a token
        
        Args:
            mint: Token mint address
            
        Returns:
            List of TokenPair
        """
        try:
            url = f"{self.BASE_URL}/latest/dex/tokens/{mint}"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            pairs = []
            
            for p in data.get("pairs", []):
                if p.get("chainId") != "solana":
                    continue
                    
                created_at = None
                if p.get("pairCreatedAt"):
                    try:
                        created_at = datetime.fromtimestamp(p["pairCreatedAt"] / 1000)
                    except:
                        pass
                
                pairs.append(TokenPair(
                    pair_address=p.get("pairAddress", ""),
                    base_token=p.get("baseToken", {}).get("address", ""),
                    base_symbol=p.get("baseToken", {}).get("symbol", "???"),
                    quote_token=p.get("quoteToken", {}).get("address", ""),
                    quote_symbol=p.get("quoteToken", {}).get("symbol", "???"),
                    price_usd=float(p.get("priceUsd", 0) or 0),
                    price_native=float(p.get("priceNative", 0) or 0),
                    price_change_5m=float(p.get("priceChange", {}).get("m5", 0) or 0),
                    price_change_1h=float(p.get("priceChange", {}).get("h1", 0) or 0),
                    price_change_6h=float(p.get("priceChange", {}).get("h6", 0) or 0),
                    price_change_24h=float(p.get("priceChange", {}).get("h24", 0) or 0),
                    volume_24h=float(p.get("volume", {}).get("h24", 0) or 0),
                    liquidity_usd=float(p.get("liquidity", {}).get("usd", 0) or 0),
                    fdv=float(p.get("fdv", 0) or 0),
                    pair_created_at=created_at,
                    dex_id=p.get("dexId", ""),
                    url=p.get("url", "")
                ))
            
            return pairs
            
        except Exception as e:
            logger.error(f"DexScreener pairs error: {e}")
            return []
    
    async def get_pair(self, pair_address: str) -> Optional[TokenPair]:
        """
        Get specific pair data
        
        Args:
            pair_address: Pair address
            
        Returns:
            TokenPair or None
        """
        try:
            url = f"{self.BASE_URL}/latest/dex/pairs/solana/{pair_address}"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            pairs = data.get("pairs", [])
            
            if not pairs:
                return None
            
            p = pairs[0]
            
            created_at = None
            if p.get("pairCreatedAt"):
                try:
                    created_at = datetime.fromtimestamp(p["pairCreatedAt"] / 1000)
                except:
                    pass
            
            return TokenPair(
                pair_address=p.get("pairAddress", ""),
                base_token=p.get("baseToken", {}).get("address", ""),
                base_symbol=p.get("baseToken", {}).get("symbol", "???"),
                quote_token=p.get("quoteToken", {}).get("address", ""),
                quote_symbol=p.get("quoteToken", {}).get("symbol", "???"),
                price_usd=float(p.get("priceUsd", 0) or 0),
                price_native=float(p.get("priceNative", 0) or 0),
                price_change_5m=float(p.get("priceChange", {}).get("m5", 0) or 0),
                price_change_1h=float(p.get("priceChange", {}).get("h1", 0) or 0),
                price_change_6h=float(p.get("priceChange", {}).get("h6", 0) or 0),
                price_change_24h=float(p.get("priceChange", {}).get("h24", 0) or 0),
                volume_24h=float(p.get("volume", {}).get("h24", 0) or 0),
                liquidity_usd=float(p.get("liquidity", {}).get("usd", 0) or 0),
                fdv=float(p.get("fdv", 0) or 0),
                pair_created_at=created_at,
                dex_id=p.get("dexId", ""),
                url=p.get("url", "")
            )
            
        except Exception as e:
            logger.error(f"DexScreener pair error: {e}")
            return None
    
    async def search_pairs(self, query: str) -> list[TokenPair]:
        """
        Search for pairs by name/symbol
        
        Args:
            query: Search string
            
        Returns:
            List of matching TokenPair
        """
        try:
            url = f"{self.BASE_URL}/latest/dex/search"
            params = {"q": query}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            pairs = []
            
            for p in data.get("pairs", []):
                if p.get("chainId") != "solana":
                    continue
                    
                created_at = None
                if p.get("pairCreatedAt"):
                    try:
                        created_at = datetime.fromtimestamp(p["pairCreatedAt"] / 1000)
                    except:
                        pass
                
                pairs.append(TokenPair(
                    pair_address=p.get("pairAddress", ""),
                    base_token=p.get("baseToken", {}).get("address", ""),
                    base_symbol=p.get("baseToken", {}).get("symbol", "???"),
                    quote_token=p.get("quoteToken", {}).get("address", ""),
                    quote_symbol=p.get("quoteToken", {}).get("symbol", "???"),
                    price_usd=float(p.get("priceUsd", 0) or 0),
                    price_native=float(p.get("priceNative", 0) or 0),
                    price_change_5m=float(p.get("priceChange", {}).get("m5", 0) or 0),
                    price_change_1h=float(p.get("priceChange", {}).get("h1", 0) or 0),
                    price_change_6h=float(p.get("priceChange", {}).get("h6", 0) or 0),
                    price_change_24h=float(p.get("priceChange", {}).get("h24", 0) or 0),
                    volume_24h=float(p.get("volume", {}).get("h24", 0) or 0),
                    liquidity_usd=float(p.get("liquidity", {}).get("usd", 0) or 0),
                    fdv=float(p.get("fdv", 0) or 0),
                    pair_created_at=created_at,
                    dex_id=p.get("dexId", ""),
                    url=p.get("url", "")
                ))
            
            return pairs[:20]  # Limit results
            
        except Exception as e:
            logger.error(f"DexScreener search error: {e}")
            return []
    
    async def get_trending_tokens(self, limit: int = 30) -> list[dict]:
        """
        Get trending Solana tokens from DexScreener
        Uses the search API to get active tokens
        
        Returns:
            List of token data dicts
        """
        try:
            # Use boosted tokens endpoint (shows promoted/active tokens)
            url = f"{self.BASE_URL}/token-boosts/top/v1"
            response = await self.client.get(url)
            
            tokens = []
            if response.status_code == 200:
                data = response.json()
                for item in data[:limit]:
                    if item.get("chainId") == "solana":
                        tokens.append({
                            "address": item.get("tokenAddress"),
                            "symbol": item.get("symbol", "???"),
                            "name": item.get("name", "Unknown"),
                            "price": 0,  # Will be fetched later
                            "liquidity": 0,
                            "url": item.get("url", "")
                        })
            
            # Also search for recent Solana pairs
            url2 = f"{self.BASE_URL}/latest/dex/search?q=SOL"
            response2 = await self.client.get(url2)
            
            if response2.status_code == 200:
                data2 = response2.json()
                for p in data2.get("pairs", [])[:limit]:
                    if p.get("chainId") == "solana":
                        base = p.get("baseToken", {})
                        liq = float(p.get("liquidity", {}).get("usd", 0) or 0)
                        
                        # Skip duplicates and low liquidity
                        if liq < 10000:
                            continue
                        if any(t["address"] == base.get("address") for t in tokens):
                            continue
                        
                        tokens.append({
                            "address": base.get("address"),
                            "symbol": base.get("symbol", "???"),
                            "name": base.get("name", "Unknown"),
                            "price": float(p.get("priceUsd", 0) or 0),
                            "liquidity": liq,
                            "volume_24h": float(p.get("volume", {}).get("h24", 0) or 0),
                            "url": p.get("url", "")
                        })
            
            logger.debug(f"DexScreener found {len(tokens)} tokens")
            return tokens[:limit]
            
        except Exception as e:
            logger.error(f"DexScreener trending error: {e}")
            return []
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = DexScreenerClient()
        
        # Search for BONK
        pairs = await client.search_pairs("BONK")
        
        if pairs:
            print(f"\nFound {len(pairs)} pairs for BONK")
            p = pairs[0]
            print(f"\nTop pair: {p.base_symbol}/{p.quote_symbol}")
            print(f"  Price: ${p.price_usd:.8f}")
            print(f"  5m: {p.price_change_5m:+.2f}%")
            print(f"  1h: {p.price_change_1h:+.2f}%")
            print(f"  24h: {p.price_change_24h:+.2f}%")
            print(f"  Volume: ${p.volume_24h:,.0f}")
            print(f"  Liquidity: ${p.liquidity_usd:,.0f}")
            print(f"  Age: {p.age_hours:.1f}h")
            print(f"  DEX: {p.dex_id}")
        
        await client.close()
    
    asyncio.run(test())
