"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                      NEXUS AI - Contract Analyzer                             ║
║                    On-chain contract inspection                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from dataclasses import dataclass
from loguru import logger
from typing import Optional
import httpx
from config import config


@dataclass
class ContractInfo:
    """SPL Token contract information"""
    mint: str
    decimals: int
    supply: int
    freeze_authority: Optional[str]
    mint_authority: Optional[str]
    is_initialized: bool
    
    @property
    def has_freeze(self) -> bool:
        return self.freeze_authority is not None
    
    @property
    def has_mint(self) -> bool:
        return self.mint_authority is not None
    
    @property
    def is_safe(self) -> bool:
        return not self.has_freeze and not self.has_mint


class ContractAnalyzer:
    """
    Analyze SPL Token contracts on-chain
    
    Checks:
    - Mint authority (can create more tokens)
    - Freeze authority (can freeze accounts)
    - Supply and decimals
    """
    
    def __init__(self, rpc_url: str = None):
        self.rpc_url = rpc_url or config.SOLANA_RPC_URL
        self.client = httpx.AsyncClient(timeout=30)
        logger.info("Contract Analyzer initialized")
    
    async def get_token_info(self, mint: str) -> Optional[ContractInfo]:
        """
        Get token contract information
        
        Args:
            mint: Token mint address
            
        Returns:
            ContractInfo or None
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "nexus",
                "method": "getAccountInfo",
                "params": [
                    mint,
                    {"encoding": "jsonParsed"}
                ]
            }
            
            response = await self.client.post(self.rpc_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if "error" in data:
                logger.error(f"RPC error: {data['error']}")
                return None
            
            result = data.get("result", {})
            value = result.get("value", {})
            
            if not value:
                logger.warning(f"Token not found: {mint}")
                return None
            
            parsed = value.get("data", {}).get("parsed", {})
            info = parsed.get("info", {})
            
            return ContractInfo(
                mint=mint,
                decimals=info.get("decimals", 0),
                supply=int(info.get("supply", 0)),
                freeze_authority=info.get("freezeAuthority"),
                mint_authority=info.get("mintAuthority"),
                is_initialized=info.get("isInitialized", False)
            )
            
        except Exception as e:
            logger.error(f"Contract analysis error: {e}")
            return None
    
    async def check_safety(self, mint: str) -> tuple[bool, list[str]]:
        """
        Quick safety check
        
        Args:
            mint: Token mint address
            
        Returns:
            (is_safe, warnings)
        """
        info = await self.get_token_info(mint)
        
        if not info:
            return False, ["Could not analyze contract"]
        
        warnings = []
        
        if info.has_mint:
            warnings.append(f"Mint authority: {info.mint_authority[:8]}...")
        
        if info.has_freeze:
            warnings.append(f"Freeze authority: {info.freeze_authority[:8]}...")
        
        return info.is_safe, warnings
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        analyzer = ContractAnalyzer()
        
        # Test with BONK
        bonk = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        
        info = await analyzer.get_token_info(bonk)
        
        if info:
            print(f"\nToken: {info.mint[:8]}...")
            print(f"Decimals: {info.decimals}")
            print(f"Supply: {info.supply:,}")
            print(f"Freeze Authority: {info.freeze_authority or 'None'}")
            print(f"Mint Authority: {info.mint_authority or 'None'}")
            print(f"\nSafe: {'✅ Yes' if info.is_safe else '❌ No'}")
        
        await analyzer.close()
    
    asyncio.run(test())
