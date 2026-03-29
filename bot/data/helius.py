"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Helius Client                             ║
║                     Enhanced Solana RPC + DAS API                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import httpx
from loguru import logger
from typing import Optional
from dataclasses import dataclass
from config import config


@dataclass
class TokenMetadata:
    """Token metadata from Helius DAS"""
    mint: str
    name: str
    symbol: str
    decimals: int
    image: Optional[str]
    description: Optional[str]


@dataclass 
class WalletBalance:
    """Wallet SOL and token balances"""
    sol_balance: float
    tokens: list[dict]


class HeliusClient:
    """
    Helius API Client
    
    Best for:
    - Enhanced RPC (faster, more reliable)
    - Digital Asset Standard (DAS) API
    - Transaction parsing
    - Webhooks
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.HELIUS_API_KEY
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"
        self.api_url = f"https://api.helius.xyz/v0"
        self.client = httpx.AsyncClient(timeout=30)
        logger.info("Helius client initialized")
    
    async def get_token_metadata(self, mint: str) -> Optional[TokenMetadata]:
        """
        Get token metadata using DAS API
        
        Args:
            mint: Token mint address
            
        Returns:
            TokenMetadata or None
        """
        try:
            url = self.rpc_url
            
            payload = {
                "jsonrpc": "2.0",
                "id": "nexus",
                "method": "getAsset",
                "params": {"id": mint}
            }
            
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if "error" in data:
                logger.warning(f"Helius error: {data['error']}")
                return None
            
            result = data.get("result", {})
            content = result.get("content", {})
            metadata = content.get("metadata", {})
            
            return TokenMetadata(
                mint=mint,
                name=metadata.get("name", "Unknown"),
                symbol=metadata.get("symbol", "???"),
                decimals=result.get("token_info", {}).get("decimals", 9),
                image=content.get("links", {}).get("image"),
                description=metadata.get("description")
            )
            
        except Exception as e:
            logger.error(f"Helius metadata error: {e}")
            return None
    
    async def get_wallet_balances(self, wallet: str) -> Optional[WalletBalance]:
        """
        Get all token balances for a wallet
        
        Args:
            wallet: Wallet address
            
        Returns:
            WalletBalance or None
        """
        try:
            # Get SOL balance
            sol_payload = {
                "jsonrpc": "2.0",
                "id": "nexus",
                "method": "getBalance",
                "params": [wallet]
            }
            
            response = await self.client.post(self.rpc_url, json=sol_payload)
            response.raise_for_status()
            sol_data = response.json()
            sol_balance = sol_data.get("result", {}).get("value", 0) / 1e9
            
            # Get token accounts
            token_payload = {
                "jsonrpc": "2.0",
                "id": "nexus",
                "method": "getTokenAccountsByOwner",
                "params": [
                    wallet,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"}
                ]
            }
            
            response = await self.client.post(self.rpc_url, json=token_payload)
            response.raise_for_status()
            token_data = response.json()
            
            tokens = []
            for account in token_data.get("result", {}).get("value", []):
                info = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                amount = info.get("tokenAmount", {})
                
                if float(amount.get("uiAmount", 0)) > 0:
                    tokens.append({
                        "mint": info.get("mint"),
                        "amount": float(amount.get("uiAmount", 0)),
                        "decimals": amount.get("decimals", 0)
                    })
            
            return WalletBalance(
                sol_balance=sol_balance,
                tokens=tokens
            )
            
        except Exception as e:
            logger.error(f"Helius balances error: {e}")
            return None
    
    async def get_token_holders(self, mint: str, limit: int = 20) -> list[dict]:
        """
        Get top token holders
        
        Args:
            mint: Token mint address
            limit: Number of holders
            
        Returns:
            List of holder data
        """
        try:
            url = f"{self.api_url}/token-metadata"
            params = {"api-key": self.api_key}
            payload = {"mintAccounts": [mint], "includeOwners": True}
            
            response = await self.client.post(url, params=params, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # This endpoint might vary - adjust based on actual response
            return data[:limit] if isinstance(data, list) else []
            
        except Exception as e:
            logger.error(f"Helius holders error: {e}")
            return []
    
    async def get_transaction(self, signature: str) -> Optional[dict]:
        """
        Get parsed transaction
        
        Args:
            signature: Transaction signature
            
        Returns:
            Parsed transaction or None
        """
        try:
            url = f"{self.api_url}/transactions"
            params = {"api-key": self.api_key}
            payload = {"transactions": [signature]}
            
            response = await self.client.post(url, params=params, json=payload)
            response.raise_for_status()
            
            data = response.json()
            return data[0] if data else None
            
        except Exception as e:
            logger.error(f"Helius transaction error: {e}")
            return None
    
    async def get_recent_tokens(self, limit: int = 30) -> list[dict]:
        """
        Get recently active tokens using DAS search
        NO RATE LIMITS!
        
        Returns:
            List of token data
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "nexus",
                "method": "searchAssets",
                "params": {
                    "tokenType": "fungible",
                    "displayOptions": {"showFungible": True},
                    "sortBy": {"sortBy": "recent_action", "sortDirection": "desc"},
                    "limit": limit
                }
            }
            
            response = await self.client.post(self.rpc_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("result", {}).get("items", [])
            
            tokens = []
            for item in items:
                content = item.get("content", {})
                metadata = content.get("metadata", {})
                token_info = item.get("token_info", {})
                
                # Skip if no symbol or looks fake
                symbol = metadata.get("symbol", "")
                if not symbol or symbol in ["SOL", "USDC", "USDT"]:
                    continue
                
                tokens.append({
                    "mint": item.get("id", ""),
                    "symbol": symbol,
                    "name": metadata.get("name", "Unknown"),
                    "supply": token_info.get("supply", 0),
                    "decimals": token_info.get("decimals", 9),
                    "price": token_info.get("price_info", {}).get("price_per_token", 0),
                    "source": "helius"
                })
            
            logger.info(f"Helius found {len(tokens)} tokens")
            return tokens
            
        except Exception as e:
            logger.error(f"Helius search error: {e}")
            return []
    
    async def get_token_price(self, mint: str) -> float:
        """
        Get token price from Helius DAS
        
        Args:
            mint: Token mint address
            
        Returns:
            Price in USD or 0
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "nexus",
                "method": "getAsset",
                "params": {"id": mint}
            }
            
            response = await self.client.post(self.rpc_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            result = data.get("result", {})
            price_info = result.get("token_info", {}).get("price_info", {})
            
            return price_info.get("price_per_token", 0)
            
        except Exception as e:
            logger.debug(f"Helius price error: {e}")
            return 0
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = HeliusClient()
        
        # Test metadata
        bonk = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        metadata = await client.get_token_metadata(bonk)
        
        if metadata:
            print(f"\nToken: {metadata.name} ({metadata.symbol})")
            print(f"  Decimals: {metadata.decimals}")
            print(f"  Image: {metadata.image}")
        else:
            print("Could not fetch metadata (check API key)")
        
        await client.close()
    
    asyncio.run(test())
