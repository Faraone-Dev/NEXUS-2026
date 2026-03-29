"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Jupiter Client                            ║
║                     Token prices, quotes, and swaps                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import httpx
from loguru import logger
from typing import Optional
from dataclasses import dataclass

from config import config


@dataclass
class TokenPrice:
    """Token price data"""
    mint: str
    price_usd: float
    liquidity: float = 0
    price_change_24h: float = 0
    
    
@dataclass 
class SwapQuote:
    """Swap quote from Jupiter"""
    input_mint: str
    output_mint: str
    in_amount: int
    out_amount: int
    price_impact: float
    route: dict


class JupiterClient:
    """
    Jupiter Aggregator API Client (V3)
    
    Requires API key from portal.jup.ag
    
    Endpoints:
    - Price API V3: Token prices
    - Swap API V1: Quotes and swaps
    """
    
    # Common tokens
    SOL = "So11111111111111111111111111111111111111112"
    USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
    
    def __init__(self):
        self.api_key = config.JUPITER_API_KEY
        self.base_url = config.JUPITER_BASE_URL or "https://api.jup.ag"
        self.price_url = config.JUPITER_PRICE_API or f"{self.base_url}/price/v3"
        self.quote_url = config.JUPITER_QUOTE_API or f"{self.base_url}/swap/v1/quote"
        self.swap_url = config.JUPITER_SWAP_API or f"{self.base_url}/swap/v1/swap"
        
        # Headers with API key
        self.headers = {}
        if self.api_key:
            self.headers["x-api-key"] = self.api_key
        
        self.client = httpx.AsyncClient(timeout=30, headers=self.headers)
        logger.info(f"Jupiter client initialized (API key: {'✓' if self.api_key else '✗'})")
    
    async def get_price(self, mint: str) -> Optional[TokenPrice]:
        """
        Get token price in USD (V3 API)
        
        Args:
            mint: Token mint address
            
        Returns:
            TokenPrice or None
        """
        try:
            params = {"ids": mint}
            
            response = await self.client.get(self.price_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # V3 format: {"mint": {"usdPrice": ..., "liquidity": ..., "priceChange24h": ...}}
            if mint in data:
                token_data = data[mint]
                return TokenPrice(
                    mint=mint,
                    price_usd=token_data.get("usdPrice", 0),
                    liquidity=token_data.get("liquidity", 0),
                    price_change_24h=token_data.get("priceChange24h", 0)
                )
                
            return None
            
        except Exception as e:
            logger.error(f"Jupiter price error: {e}")
            return None
    
    async def get_prices(self, mints: list[str]) -> dict[str, float]:
        """
        Get multiple token prices (V3 API)
        
        Args:
            mints: List of token mint addresses (max 50)
            
        Returns:
            Dict of mint -> price_usd
        """
        try:
            # V3 allows up to 50 ids per request
            params = {"ids": ",".join(mints[:50])}
            
            response = await self.client.get(self.price_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # V3 format: {"mint": {"usdPrice": ...}, ...}
            prices = {}
            for mint in mints:
                if mint in data:
                    prices[mint] = data[mint].get("usdPrice", 0)
                    
            return prices
            
        except Exception as e:
            logger.error(f"Jupiter prices error: {e}")
            return {}
    
    async def get_quote(
        self, 
        input_mint: str, 
        output_mint: str, 
        amount: int,
        slippage_bps: int = 50
    ) -> Optional[SwapQuote]:
        """
        Get swap quote (Swap API V1)
        
        Args:
            input_mint: Input token mint
            output_mint: Output token mint  
            amount: Amount in smallest units (lamports/tokens)
            slippage_bps: Slippage in basis points (50 = 0.5%)
            
        Returns:
            SwapQuote or None
        """
        try:
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": slippage_bps
            }
            
            response = await self.client.get(self.quote_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            return SwapQuote(
                input_mint=data["inputMint"],
                output_mint=data["outputMint"],
                in_amount=int(data["inAmount"]),
                out_amount=int(data["outAmount"]),
                price_impact=float(data.get("priceImpactPct", 0)),
                route=data
            )
            
        except Exception as e:
            logger.error(f"Jupiter quote error: {e}")
            return None
    
    async def get_swap_transaction(
        self,
        quote: SwapQuote,
        user_public_key: str
    ) -> Optional[str]:
        """
        Get serialized swap transaction (Swap API V1)
        
        Args:
            quote: SwapQuote from get_quote()
            user_public_key: User's wallet address
            
        Returns:
            Base64 encoded transaction or None
        """
        try:
            payload = {
                "quoteResponse": quote.route,
                "userPublicKey": user_public_key,
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": "auto"
            }
            
            response = await self.client.post(self.swap_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            return data.get("swapTransaction")
            
        except Exception as e:
            logger.error(f"Jupiter swap error: {e}")
            return None
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = JupiterClient()
        
        # Test price
        sol_price = await client.get_price(JupiterClient.SOL)
        print(f"SOL Price: ${sol_price.price_usd:.2f}" if sol_price else "Failed")
        
        # Test quote (0.1 SOL -> USDC)
        quote = await client.get_quote(
            JupiterClient.SOL,
            JupiterClient.USDC,
            100_000_000  # 0.1 SOL in lamports
        )
        if quote:
            print(f"Quote: {quote.in_amount/1e9:.4f} SOL -> {quote.out_amount/1e6:.2f} USDC")
            print(f"Price Impact: {quote.price_impact:.4f}%")
        
        await client.close()
    
    asyncio.run(test())
