"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     NEXUS AI - GeckoTerminal/PumpSwap Client                   ║
║               Token HOT da Pump.fun via GeckoTerminal API - GRATIS!           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

GeckoTerminal API fornisce accesso ai pool PumpSwap (token Pump.fun graduati)
e a tutti i DEX su Solana. API pubblica, nessun key richiesto!
"""

import httpx
from dataclasses import dataclass
from typing import Optional
from loguru import logger
from datetime import datetime


@dataclass
class PumpToken:
    """Token data from PumpSwap/GeckoTerminal"""
    mint: str
    symbol: str
    name: str
    description: str = ""
    image_url: str = ""
    
    # Market data
    price_usd: float = 0.0
    price_sol: float = 0.0
    market_cap: float = 0.0
    fdv: float = 0.0
    liquidity_usd: float = 0.0
    
    # Volume & activity
    volume_24h: float = 0.0
    volume_1h: float = 0.0
    buys_24h: int = 0
    sells_24h: int = 0
    buyers_24h: int = 0
    sellers_24h: int = 0
    
    # Price changes
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    
    # Pool info
    pool_address: str = ""
    dex: str = "pumpswap"
    created_at: Optional[datetime] = None
    
    @property
    def age_hours(self) -> float:
        """Token age in hours"""
        if self.created_at:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            # Ensure created_at is aware
            if self.created_at.tzinfo is None:
                created = self.created_at.replace(tzinfo=timezone.utc)
            else:
                created = self.created_at
            return (now - created).total_seconds() / 3600
        return 0.0
    
    @property
    def buy_sell_ratio(self) -> float:
        """Buy/Sell ratio (>1 = more buying)"""
        if self.sells_24h > 0:
            return self.buys_24h / self.sells_24h
        return self.buys_24h if self.buys_24h > 0 else 0


class PumpFunClient:
    """
    GeckoTerminal API Client per PumpSwap tokens
    
    GRATIS - No API key needed!
    Limite: 30 calls/min (ma possiamo cachare)
    
    Features:
    - PumpSwap pools (Pump.fun tokens graduati su Raydium)
    - Nuovi pool su Solana
    - Volume, liquidità, transazioni
    - Price changes real-time
    """
    
    BASE_URL = "https://api.geckoterminal.com/api/v2"
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15.0,
            headers={
                "Accept": "application/json",
                "User-Agent": "NEXUS-AI-Bot/1.0"
            }
        )
        self._cache = {}
        self._cache_time = 0
        logger.info("🦎 GeckoTerminal/PumpSwap client initialized (FREE!)")
    
    async def get_pumpswap_tokens(self, limit: int = 30) -> list[PumpToken]:
        """
        Get tokens from PumpSwap (Pump.fun graduati)
        
        Usa GeckoTerminal API - i pool con dex="pumpswap" sono
        token che hanno passato la bonding curve su Pump.fun!
        
        Returns:
            List of PumpToken from PumpSwap pools
        """
        import time
        
        # Cache per 30 secondi per rispettare rate limit
        cache_key = "pumpswap_pools"
        now = time.time()
        if cache_key in self._cache and now - self._cache_time < 30:
            logger.debug("📦 Using cached PumpSwap data")
            return self._cache[cache_key]
        
        try:
            # GeckoTerminal: Get Solana pools sorted by volume
            url = f"{self.BASE_URL}/networks/solana/pools"
            params = {"page": 1}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            tokens = []
            for pool in data.get("data", []):
                attrs = pool.get("attributes", {})
                relationships = pool.get("relationships", {})
                
                # Get DEX name
                dex_data = relationships.get("dex", {}).get("data", {})
                dex_name = dex_data.get("id", "unknown")
                
                # Only PumpSwap pools (Pump.fun tokens)
                if "pumpswap" not in dex_name.lower():
                    continue
                
                # Parse token data
                token = self._parse_gecko_pool(pool)
                if token and token.volume_24h > 0:
                    tokens.append(token)
            
            # Sort by 24h volume (most active first)
            tokens.sort(key=lambda x: x.volume_24h, reverse=True)
            tokens = tokens[:limit]
            
            # Cache results
            self._cache[cache_key] = tokens
            self._cache_time = now
            
            logger.info(f"🦎 GeckoTerminal: found {len(tokens)} PumpSwap tokens")
            return tokens
            
        except Exception as e:
            logger.error(f"GeckoTerminal PumpSwap error: {e}")
            return []
    
    async def get_new_tokens(self, limit: int = 30) -> list[PumpToken]:
        """
        Get newest tokens on Solana (from all DEXes)
        
        Returns:
            List of PumpToken sorted by creation time
        """
        try:
            # GeckoTerminal: new pools endpoint
            url = f"{self.BASE_URL}/networks/solana/new_pools"
            params = {"page": 1}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            tokens = []
            for pool in data.get("data", []):
                token = self._parse_gecko_pool(pool)
                if token:
                    tokens.append(token)
            
            # Prioritize PumpSwap tokens
            pumpswap_tokens = [t for t in tokens if t.dex == "pumpswap"]
            other_tokens = [t for t in tokens if t.dex != "pumpswap"]
            
            result = pumpswap_tokens + other_tokens
            logger.info(f"🆕 GeckoTerminal: {len(pumpswap_tokens)} PumpSwap + {len(other_tokens)} other new tokens")
            return result[:limit]
            
        except Exception as e:
            logger.error(f"GeckoTerminal new pools error: {e}")
            return []
    
    async def get_trending_tokens(self, limit: int = 30) -> list[PumpToken]:
        """
        Get trending/hot tokens (high volume)
        
        Returns:
            List of PumpToken sorted by activity
        """
        try:
            # GeckoTerminal: trending pools
            url = f"{self.BASE_URL}/networks/solana/trending_pools"
            params = {"page": 1}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            tokens = []
            for pool in data.get("data", []):
                token = self._parse_gecko_pool(pool)
                if token and token.volume_24h > 1000:  # Min $1k volume
                    tokens.append(token)
            
            # Prioritize PumpSwap
            pumpswap = [t for t in tokens if t.dex == "pumpswap"]
            others = [t for t in tokens if t.dex != "pumpswap"]
            
            logger.info(f"🔥 GeckoTerminal: {len(pumpswap)} PumpSwap + {len(others)} other trending")
            return (pumpswap + others)[:limit]
            
        except Exception as e:
            logger.error(f"GeckoTerminal trending error: {e}")
            return []
    
    async def get_token_details(self, mint: str) -> Optional[PumpToken]:
        """
        Get detailed token info from GeckoTerminal
        
        Args:
            mint: Token mint address
            
        Returns:
            PumpToken or None
        """
        try:
            # Search for pools containing this token
            url = f"{self.BASE_URL}/networks/solana/tokens/{mint}/pools"
            params = {"page": 1}
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            pools = data.get("data", [])
            if not pools:
                return None
            
            # Return first pool data
            return self._parse_gecko_pool(pools[0])
            
        except Exception as e:
            logger.debug(f"GeckoTerminal token details error: {e}")
            return None
    
    def _parse_gecko_pool(self, pool: dict) -> Optional[PumpToken]:
        """Parse GeckoTerminal pool response into PumpToken"""
        try:
            attrs = pool.get("attributes", {})
            relationships = pool.get("relationships", {})
            
            # Pool name is "TOKEN / SOL"
            name = attrs.get("name", "")
            symbol = name.split(" /")[0] if " /" in name else name[:10]
            
            # Get base token mint
            base_token_data = relationships.get("base_token", {}).get("data", {})
            token_id = base_token_data.get("id", "")
            # Format: "solana_ADDRESS"
            mint = token_id.replace("solana_", "") if token_id.startswith("solana_") else token_id
            
            # Get DEX
            dex_data = relationships.get("dex", {}).get("data", {})
            dex_name = dex_data.get("id", "unknown")
            
            # Parse volume
            volume_usd = attrs.get("volume_usd", {})
            volume_24h = float(volume_usd.get("h24", 0) or 0)
            volume_1h = float(volume_usd.get("h1", 0) or 0)
            
            # Parse transactions
            txns = attrs.get("transactions", {})
            txns_24h = txns.get("h24", {})
            
            # Parse price changes
            price_change = attrs.get("price_change_percentage", {})
            
            # Parse creation time
            created_str = attrs.get("pool_created_at", "")
            created_at = None
            if created_str:
                try:
                    created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except:
                    pass
            
            return PumpToken(
                mint=mint,
                symbol=symbol,
                name=name,
                pool_address=attrs.get("address", ""),
                dex=dex_name,
                
                # Prices
                price_usd=float(attrs.get("base_token_price_usd", 0) or 0),
                price_sol=float(attrs.get("base_token_price_native_currency", 0) or 0),
                
                # Market data
                fdv=float(attrs.get("fdv_usd", 0) or 0),
                market_cap=float(attrs.get("market_cap_usd", 0) or attrs.get("fdv_usd", 0) or 0),
                liquidity_usd=float(attrs.get("reserve_in_usd", 0) or 0),
                
                # Volume
                volume_24h=volume_24h,
                volume_1h=volume_1h,
                
                # Transactions
                buys_24h=int(txns_24h.get("buys", 0) or 0),
                sells_24h=int(txns_24h.get("sells", 0) or 0),
                buyers_24h=int(txns_24h.get("buyers", 0) or 0),
                sellers_24h=int(txns_24h.get("sellers", 0) or 0),
                
                # Price changes
                price_change_1h=float(price_change.get("h1", 0) or 0),
                price_change_24h=float(price_change.get("h24", 0) or 0),
                
                # Time
                created_at=created_at
            )
            
        except Exception as e:
            logger.debug(f"Error parsing GeckoTerminal pool: {e}")
            return None
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = PumpFunClient()
        
        print("=" * 60)
        print("   🦎 GECKOTERMINAL PUMPSWAP TEST")
        print("=" * 60)
        
        # Get PumpSwap tokens
        pumpswap = await client.get_pumpswap_tokens(limit=10)
        if pumpswap:
            print(f"\n🎰 TOP 10 PUMPSWAP TOKENS (by volume):")
            for i, token in enumerate(pumpswap, 1):
                age = f"{token.age_hours:.1f}h" if token.age_hours > 0 else "?"
                print(f"   {i}. {token.symbol}")
                print(f"      💰 ${token.volume_24h:,.0f} vol | ${token.fdv:,.0f} FDV")
                print(f"      📊 {token.buys_24h:,} buys / {token.sells_24h:,} sells")
                print(f"      📈 {token.price_change_24h:+.1f}% (24h) | Age: {age}")
        
        # Get trending
        trending = await client.get_trending_tokens(limit=5)
        if trending:
            print(f"\n🔥 TOP 5 TRENDING:")
            for token in trending:
                print(f"   - {token.symbol} ({token.dex}): ${token.volume_24h:,.0f}")
        
        # Get new
        new = await client.get_new_tokens(limit=5)
        if new:
            print(f"\n🆕 NEWEST POOLS:")
            for token in new:
                age = f"{token.age_hours:.1f}h" if token.age_hours > 0 else "just created"
                print(f"   - {token.symbol} ({token.dex}): {age}")
        
        await client.close()
        print("\n✅ GeckoTerminal working!")
    
    asyncio.run(test())
