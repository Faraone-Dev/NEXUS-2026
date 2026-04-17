"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Whale Tracker                             ║
║                     Track big wallet movements via Helius                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import httpx
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from config import config
from .jupiter import JupiterClient


@dataclass
class WhaleTransaction:
    """A large transaction from a notable wallet"""
    signature: str
    wallet: str
    wallet_label: Optional[str]
    token_mint: str
    token_symbol: str
    action: str  # BUY / SELL / TRANSFER
    amount_tokens: float
    amount_usd: float
    timestamp: str
    
    # Context
    is_known_whale: bool
    wallet_sol_balance: Optional[float] = None
    wallet_token_holdings: Optional[int] = None


@dataclass
class WalletProfile:
    """Profile of a tracked wallet"""
    address: str
    label: Optional[str]
    category: str  # whale / influencer / smart_money / degen
    total_value_usd: float
    win_rate: Optional[float]
    avg_hold_time: Optional[float]
    notable_tokens: list[str]


class WhaleTracker:
    """
    Track whale and smart money movements on Solana
    
    Features:
    - Real-time large transaction detection
    - Known wallet database
    - Transaction pattern analysis
    - Token accumulation/distribution alerts
    """
    
    # Known whales and smart money (expand this list)
    KNOWN_WALLETS = {
        # Big players
        "GUfCR9mK6azb9vcpsxgXyj7XRPAKJd4KMHTTVvtncGgp": {"label": "Jupiter Whale", "category": "whale"},
        "DBkStwWHpG5MaHjQHHbEw5LKQgeFjxjWw7EfNdsPXyVD": {"label": "Solana Whale #1", "category": "whale"},
        "7VTw49DyvH5Z5PH3MjxbN3qv1r5vw7dG3QwKSYvjx3pU": {"label": "DeFi Whale", "category": "whale"},
        
        # Known smart money
        "4rXM9eoLPsKqDqcmtZC7wVnGvhHwJr1cpKzJ9sxzFspf": {"label": "Smart Money #1", "category": "smart_money"},
        "HN7cABqLq46Es1jh92dQQisAq662SmxELLLsHHe4YWrH": {"label": "Smart Money #2", "category": "smart_money"},
        
        # DEX/Aggregator wallets (for volume tracking)
        "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": {"label": "Jupiter Aggregator", "category": "protocol"},
        "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": {"label": "Orca Whirlpool", "category": "protocol"},
    }
    
    # Minimum USD value to consider as whale transaction
    MIN_WHALE_USD = 50_000
    
    # Minimum USD for tracking
    MIN_TRACK_USD = 10_000
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.HELIUS_API_KEY
        self.rpc_url = "https://mainnet.helius-rpc.com"
        self.api_url = "https://api.helius.xyz/v0"
        self._rpc_params = {"api-key": self.api_key}
        self.client = httpx.AsyncClient(timeout=30)
        self.price_client = JupiterClient()
        
        # Cache for wallet profiles
        self.wallet_cache: dict[str, WalletProfile] = {}
        self._price_cache: dict[str, float] = {}
        
        logger.info("🐋 Whale Tracker initialized")
    
    async def get_recent_token_transactions(
        self,
        token_mint: str,
        limit: int = 50,
        min_usd: float = None
    ) -> list[WhaleTransaction]:
        """
        Get recent large transactions for a token
        
        Args:
            token_mint: Token mint address
            limit: Max transactions to fetch
            min_usd: Minimum USD value to include
            
        Returns:
            List of WhaleTransaction
        """
        min_usd = min_usd or self.MIN_TRACK_USD
        
        try:
            # Use Helius parsed transaction history API
            url = f"{self.api_url}/addresses/{token_mint}/transactions"
            params = {
                "api-key": self.api_key,
                "limit": limit
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            transactions = response.json()
            whale_txs = []
            token_price_usd = await self._get_token_price(token_mint)
            
            for tx in transactions:
                # Parse the transaction
                whale_tx = await self._parse_transaction(tx, token_mint, min_usd, token_price_usd)
                if whale_tx:
                    whale_txs.append(whale_tx)
            
            return whale_txs
            
        except Exception as e:
            logger.error(f"Whale tracker error: {e}")
            return []
    
    async def get_wallet_transactions(
        self,
        wallet: str,
        limit: int = 20
    ) -> list[dict]:
        """
        Get recent transactions for a wallet
        
        Args:
            wallet: Wallet address
            limit: Max transactions
            
        Returns:
            List of parsed transactions
        """
        try:
            url = f"{self.api_url}/addresses/{wallet}/transactions"
            params = {
                "api-key": self.api_key,
                "limit": limit
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Wallet transactions error: {e}")
            return []
    
    async def analyze_token_flow(self, token_mint: str) -> dict:
        """
        Analyze buy/sell flow for a token
        
        Returns:
            Flow analysis with whale activity
        """
        transactions = await self.get_recent_token_transactions(token_mint, limit=100)
        
        if not transactions:
            return {
                "token_mint": token_mint,
                "whale_buys": 0,
                "whale_sells": 0,
                "whale_buy_volume": 0,
                "whale_sell_volume": 0,
                "net_flow": 0,
                "signal": "NEUTRAL",
                "notable_wallets": []
            }
        
        whale_buys = 0
        whale_sells = 0
        whale_buy_volume = 0.0
        whale_sell_volume = 0.0
        notable_wallets = set()
        
        for tx in transactions:
            if tx.action == "BUY":
                if tx.amount_usd >= self.MIN_WHALE_USD:
                    whale_buys += 1
                    whale_buy_volume += tx.amount_usd
                    if tx.is_known_whale:
                        notable_wallets.add(tx.wallet_label or tx.wallet[:8])
                        
            elif tx.action == "SELL":
                if tx.amount_usd >= self.MIN_WHALE_USD:
                    whale_sells += 1
                    whale_sell_volume += tx.amount_usd
                    if tx.is_known_whale:
                        notable_wallets.add(tx.wallet_label or tx.wallet[:8])
        
        net_flow = whale_buy_volume - whale_sell_volume
        
        # Determine signal
        if whale_buys > whale_sells * 2 and net_flow > 100_000:
            signal = "STRONG_BUY"
        elif whale_buys > whale_sells and net_flow > 50_000:
            signal = "BUY"
        elif whale_sells > whale_buys * 2 and net_flow < -100_000:
            signal = "STRONG_SELL"
        elif whale_sells > whale_buys and net_flow < -50_000:
            signal = "SELL"
        else:
            signal = "NEUTRAL"
        
        return {
            "token_mint": token_mint,
            "whale_buys": whale_buys,
            "whale_sells": whale_sells,
            "whale_buy_volume": whale_buy_volume,
            "whale_sell_volume": whale_sell_volume,
            "net_flow": net_flow,
            "signal": signal,
            "notable_wallets": list(notable_wallets)
        }
    
    async def check_whale_accumulation(
        self,
        token_mint: str,
        hours: int = 24
    ) -> dict:
        """
        Check if whales are accumulating a token
        
        Returns:
            Accumulation analysis
        """
        # Get recent transactions
        transactions = await self.get_recent_token_transactions(token_mint, limit=200)
        
        # Filter by time
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [tx for tx in transactions if datetime.fromisoformat(tx.timestamp) > cutoff]
        
        # Analyze per wallet
        wallet_activity = {}
        
        for tx in recent:
            if tx.amount_usd < self.MIN_TRACK_USD:
                continue
                
            wallet = tx.wallet
            if wallet not in wallet_activity:
                wallet_activity[wallet] = {
                    "label": tx.wallet_label,
                    "is_whale": tx.is_known_whale,
                    "buys": 0,
                    "sells": 0,
                    "buy_volume": 0,
                    "sell_volume": 0
                }
            
            if tx.action == "BUY":
                wallet_activity[wallet]["buys"] += 1
                wallet_activity[wallet]["buy_volume"] += tx.amount_usd
            elif tx.action == "SELL":
                wallet_activity[wallet]["sells"] += 1
                wallet_activity[wallet]["sell_volume"] += tx.amount_usd
        
        # Find accumulators (more buys than sells)
        accumulators = []
        distributors = []
        
        for wallet, data in wallet_activity.items():
            net = data["buy_volume"] - data["sell_volume"]
            if net > 0 and data["buys"] > data["sells"]:
                accumulators.append({
                    "wallet": wallet,
                    "label": data["label"],
                    "is_whale": data["is_whale"],
                    "net_bought": net,
                    "buys": data["buys"]
                })
            elif net < 0 and data["sells"] > data["buys"]:
                distributors.append({
                    "wallet": wallet,
                    "label": data["label"],
                    "is_whale": data["is_whale"],
                    "net_sold": abs(net),
                    "sells": data["sells"]
                })
        
        # Sort by volume
        accumulators.sort(key=lambda x: x["net_bought"], reverse=True)
        distributors.sort(key=lambda x: x["net_sold"], reverse=True)
        
        # Calculate overall signal
        total_accumulated = sum(a["net_bought"] for a in accumulators)
        total_distributed = sum(d["net_sold"] for d in distributors)
        
        whale_accumulators = [a for a in accumulators if a["is_whale"]]
        whale_distributors = [d for d in distributors if d["is_whale"]]
        
        if len(whale_accumulators) > len(whale_distributors) and total_accumulated > total_distributed:
            signal = "ACCUMULATING"
        elif len(whale_distributors) > len(whale_accumulators) and total_distributed > total_accumulated:
            signal = "DISTRIBUTING"
        else:
            signal = "NEUTRAL"
        
        return {
            "token_mint": token_mint,
            "period_hours": hours,
            "signal": signal,
            "total_accumulated_usd": total_accumulated,
            "total_distributed_usd": total_distributed,
            "top_accumulators": accumulators[:5],
            "top_distributors": distributors[:5],
            "whale_accumulators_count": len(whale_accumulators),
            "whale_distributors_count": len(whale_distributors)
        }
    
    async def get_whale_alerts_for_token(self, token_mint: str) -> list[dict]:
        """
        Get whale alert summary for telegram/dashboard
        
        Returns:
            List of alert dicts
        """
        transactions = await self.get_recent_token_transactions(
            token_mint, 
            limit=50, 
            min_usd=self.MIN_WHALE_USD
        )
        
        alerts = []
        for tx in transactions:
            emoji = "🐋" if tx.amount_usd >= 100_000 else "🔵"
            action_emoji = "🟢" if tx.action == "BUY" else "🔴"
            
            alerts.append({
                "emoji": emoji,
                "action": tx.action,
                "action_emoji": action_emoji,
                "wallet": tx.wallet[:8] + "...",
                "wallet_label": tx.wallet_label,
                "amount_usd": tx.amount_usd,
                "amount_tokens": tx.amount_tokens,
                "timestamp": tx.timestamp,
                "is_known": tx.is_known_whale
            })
        
        return alerts
    
    def _normalize_token_amount(self, transfer: dict) -> Optional[float]:
        """Normalize token amount from Helius transfer payload."""
        if not transfer:
            return None
        amount = transfer.get("tokenAmount")

        # Direct numeric amount
        if isinstance(amount, (int, float)):
            return float(amount)
        if isinstance(amount, str):
            try:
                return float(amount)
            except ValueError:
                pass

        # Nested objects
        if isinstance(amount, dict):
            if "uiAmount" in amount and amount["uiAmount"] is not None:
                try:
                    return float(amount["uiAmount"])
                except (TypeError, ValueError):
                    pass
            decimals = amount.get("decimals") or amount.get("tokenDecimals")
            token_amount = amount.get("tokenAmount") or amount.get("amount")
            if token_amount is not None and decimals is not None:
                try:
                    return float(token_amount) / (10 ** int(decimals))
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

        raw = transfer.get("rawTokenAmount")
        if isinstance(raw, dict):
            token_amount = raw.get("tokenAmount")
            decimals = raw.get("decimals")
            if token_amount is not None and decimals is not None:
                try:
                    return float(token_amount) / (10 ** int(decimals))
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

        ui_amount = transfer.get("uiAmountString")
        if ui_amount is not None:
            try:
                return float(ui_amount)
            except ValueError:
                pass

        return None

    async def _get_token_price(self, token_mint: str) -> Optional[float]:
        """Retrieve token price in USD using Jupiter API with simple caching."""
        if not token_mint:
            return None
        if token_mint in self._price_cache:
            return self._price_cache[token_mint]
        try:
            price = await self.price_client.get_price(token_mint)
            if price and price.price_usd:
                value = float(price.price_usd)
                self._price_cache[token_mint] = value
                return value
        except Exception as exc:
            logger.debug(f"Failed to fetch price for {token_mint[:8]}: {exc}")
        return None

    async def _parse_transaction(
        self,
        tx: dict,
        token_mint: str,
        min_usd: float,
        price_usd: Optional[float] = None
    ) -> Optional[WhaleTransaction]:
        """Parse a Helius transaction into WhaleTransaction"""
        try:
            # Extract relevant info from Helius parsed format
            signature = tx.get("signature", "")
            timestamp = tx.get("timestamp", 0)
            
            # Look for token transfers
            token_transfers = tx.get("tokenTransfers", [])
            
            for transfer in token_transfers:
                if transfer.get("mint") != token_mint:
                    continue
                
                amount = self._normalize_token_amount(transfer)
                if amount is None or amount <= 0:
                    continue

                # Attempt to derive USD value
                amount_usd = transfer.get("amountUSD")
                if isinstance(amount_usd, dict):
                    amount_usd = amount_usd.get("value") or amount_usd.get("amount")
                if isinstance(amount_usd, str):
                    try:
                        amount_usd = float(amount_usd)
                    except ValueError:
                        amount_usd = None

                token_price = price_usd
                local_price = transfer.get("tokenPrice") or transfer.get("price")
                if isinstance(local_price, dict):
                    local_price = local_price.get("price") or local_price.get("value")
                if isinstance(local_price, str):
                    try:
                        local_price = float(local_price)
                    except ValueError:
                        local_price = None
                if token_price is None and isinstance(local_price, (int, float)):
                    token_price = float(local_price)

                if amount_usd is None and token_price is not None:
                    amount_usd = amount * token_price

                if not isinstance(amount_usd, (int, float)):
                    continue
                amount_usd = float(amount_usd)

                if amount_usd < min_usd:
                    continue
                
                # Determine direction
                from_wallet = transfer.get("fromUserAccount", "")
                to_wallet = transfer.get("toUserAccount", "")
                
                # Check if from/to is a known DEX
                dex_wallets = {"JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4", "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"}
                
                if from_wallet in dex_wallets:
                    action = "BUY"
                    wallet = to_wallet
                elif to_wallet in dex_wallets:
                    action = "SELL"
                    wallet = from_wallet
                else:
                    action = "TRANSFER"
                    wallet = from_wallet
                
                # Check if known whale
                wallet_info = self.KNOWN_WALLETS.get(wallet, {})
                is_known = bool(wallet_info)
                
                return WhaleTransaction(
                    signature=signature,
                    wallet=wallet,
                    wallet_label=wallet_info.get("label"),
                    token_mint=token_mint,
                    token_symbol="",  # Would need to fetch
                    action=action,
                    amount_tokens=amount,
                    amount_usd=amount_usd,
                    timestamp=datetime.fromtimestamp(timestamp).isoformat() if timestamp else datetime.now().isoformat(),
                    is_known_whale=is_known
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None
    
    def is_known_wallet(self, address: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if wallet is in known list
        
        Returns:
            (is_known, label, category)
        """
        info = self.KNOWN_WALLETS.get(address)
        if info:
            return True, info.get("label"), info.get("category")
        return False, None, None
    
    def add_known_wallet(self, address: str, label: str, category: str = "whale"):
        """Add a wallet to the known list"""
        self.KNOWN_WALLETS[address] = {"label": label, "category": category}
        logger.info(f"Added known wallet: {label} ({address[:8]}...)")
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        await self.price_client.close()


# Test
if __name__ == "__main__":
    async def test():
        tracker = WhaleTracker()
        
        # Test with BONK
        bonk = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        
        print("🐋 Testing whale tracker...")
        
        # Check flow
        flow = await tracker.analyze_token_flow(bonk)
        print(f"\nToken Flow Analysis:")
        print(f"  Whale Buys: {flow['whale_buys']}")
        print(f"  Whale Sells: {flow['whale_sells']}")
        print(f"  Net Flow: ${flow['net_flow']:,.0f}")
        print(f"  Signal: {flow['signal']}")
        
        # Check accumulation
        accum = await tracker.check_whale_accumulation(bonk, hours=24)
        print(f"\nAccumulation Analysis:")
        print(f"  Signal: {accum['signal']}")
        print(f"  Accumulated: ${accum['total_accumulated_usd']:,.0f}")
        print(f"  Distributed: ${accum['total_distributed_usd']:,.0f}")
        
        await tracker.close()
    
    asyncio.run(test())
