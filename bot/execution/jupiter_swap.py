"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Jupiter Swap                              ║
║                      Execute swaps via Jupiter aggregator                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import base64
import base58
from dataclasses import dataclass
from loguru import logger
from typing import Optional
from config import config
from data.jupiter import JupiterClient, SwapQuote

try:
    from solders.keypair import Keypair
    from solders.transaction import VersionedTransaction
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Confirmed
    SOLANA_AVAILABLE = True
except ImportError:
    SOLANA_AVAILABLE = False
    logger.warning("Solana SDK not installed - execution disabled")


@dataclass
class SwapResult:
    """Result of a swap execution"""
    success: bool
    signature: Optional[str]
    input_amount: float
    output_amount: float
    price_impact: float
    error: Optional[str] = None


class JupiterSwap:
    """
    Execute swaps via Jupiter
    
    Features:
    - Best route aggregation
    - MEV protection
    - Slippage control
    """
    
    # Common tokens
    SOL = "So11111111111111111111111111111111111111112"
    USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    
    def __init__(self):
        self.jupiter = JupiterClient()
        self.wallet = None
        self.rpc = None
        
        if SOLANA_AVAILABLE and config.SOLANA_PRIVATE_KEY:
            try:
                # Decode private key
                key_bytes = base58.b58decode(config.SOLANA_PRIVATE_KEY)
                self.wallet = Keypair.from_bytes(key_bytes)
                self.rpc = AsyncClient(config.SOLANA_RPC_URL)
                logger.info(f"Wallet loaded: {self.wallet.pubkey()}")
            except Exception as e:
                logger.error(f"Failed to load wallet: {e}")
        else:
            logger.warning("Wallet not configured - dry run mode only")
    
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: float,
        input_decimals: int = 9,
        slippage_bps: int = 50
    ) -> Optional[SwapQuote]:
        """
        Get swap quote
        
        Args:
            input_mint: Input token mint
            output_mint: Output token mint
            amount: Amount in human readable (e.g., 0.1 SOL)
            input_decimals: Decimals of input token
            slippage_bps: Slippage tolerance (50 = 0.5%)
            
        Returns:
            SwapQuote or None
        """
        # Convert to smallest units
        amount_lamports = int(amount * (10 ** input_decimals))
        
        return await self.jupiter.get_quote(
            input_mint, output_mint, amount_lamports, slippage_bps
        )
    
    async def execute_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: float,
        input_decimals: int = 9,
        slippage_bps: int = 50
    ) -> SwapResult:
        """
        Execute a swap
        
        Args:
            input_mint: Input token mint
            output_mint: Output token mint
            amount: Amount to swap
            input_decimals: Decimals of input token
            slippage_bps: Slippage tolerance
            
        Returns:
            SwapResult
        """
        # DRY RUN check
        if config.DRY_RUN:
            logger.info("🟡 DRY RUN - Simulating swap...")
            
            quote = await self.get_quote(
                input_mint, output_mint, amount, input_decimals, slippage_bps
            )
            
            if quote:
                return SwapResult(
                    success=True,
                    signature="DRY_RUN_" + "0" * 64,
                    input_amount=amount,
                    output_amount=quote.out_amount / (10 ** 6),  # Assume USDC output
                    price_impact=quote.price_impact,
                    error="DRY RUN - No actual swap"
                )
            else:
                return SwapResult(
                    success=False,
                    signature=None,
                    input_amount=amount,
                    output_amount=0,
                    price_impact=0,
                    error="Failed to get quote"
                )
        
        # LIVE execution
        if not self.wallet or not self.rpc:
            return SwapResult(
                success=False,
                signature=None,
                input_amount=amount,
                output_amount=0,
                price_impact=0,
                error="Wallet not configured"
            )
        
        try:
            # 1. Get quote
            quote = await self.get_quote(
                input_mint, output_mint, amount, input_decimals, slippage_bps
            )
            
            if not quote:
                return SwapResult(
                    success=False,
                    signature=None,
                    input_amount=amount,
                    output_amount=0,
                    price_impact=0,
                    error="Failed to get quote"
                )
            
            # 2. Get swap transaction
            swap_tx_b64 = await self.jupiter.get_swap_transaction(
                quote, str(self.wallet.pubkey())
            )
            
            if not swap_tx_b64:
                return SwapResult(
                    success=False,
                    signature=None,
                    input_amount=amount,
                    output_amount=0,
                    price_impact=quote.price_impact,
                    error="Failed to build swap transaction"
                )
            
            # 3. Sign and send
            tx_bytes = base64.b64decode(swap_tx_b64)
            tx = VersionedTransaction.from_bytes(tx_bytes)
            tx.sign([self.wallet])
            
            # Send transaction
            result = await self.rpc.send_transaction(
                tx,
                opts={"skip_preflight": True}
            )
            
            signature = str(result.value)
            logger.info(f"✅ Swap sent: {signature}")
            
            # Wait for confirmation
            await self.rpc.confirm_transaction(signature, commitment=Confirmed)
            logger.info(f"✅ Swap confirmed!")
            
            return SwapResult(
                success=True,
                signature=signature,
                input_amount=amount,
                output_amount=quote.out_amount / (10 ** 6),
                price_impact=quote.price_impact
            )
            
        except Exception as e:
            logger.error(f"Swap execution error: {e}")
            return SwapResult(
                success=False,
                signature=None,
                input_amount=amount,
                output_amount=0,
                price_impact=0,
                error=str(e)
            )
    
    async def buy_token(
        self,
        token_mint: str,
        sol_amount: float,
        slippage_bps: int = 100
    ) -> SwapResult:
        """
        Buy token with SOL
        
        Args:
            token_mint: Token to buy
            sol_amount: SOL to spend
            slippage_bps: Slippage (100 = 1% for memecoins)
            
        Returns:
            SwapResult
        """
        logger.info(f"🛒 Buying {sol_amount} SOL worth of {token_mint[:8]}...")
        
        return await self.execute_swap(
            self.SOL,
            token_mint,
            sol_amount,
            input_decimals=9,
            slippage_bps=slippage_bps
        )
    
    async def sell_token(
        self,
        token_mint: str,
        token_amount: float,
        token_decimals: int = 9,
        slippage_bps: int = 100
    ) -> SwapResult:
        """
        Sell token for SOL
        
        Args:
            token_mint: Token to sell
            token_amount: Amount to sell
            token_decimals: Token decimals
            slippage_bps: Slippage
            
        Returns:
            SwapResult
        """
        logger.info(f"💰 Selling {token_amount} of {token_mint[:8]}...")
        
        return await self.execute_swap(
            token_mint,
            self.SOL,
            token_amount,
            input_decimals=token_decimals,
            slippage_bps=slippage_bps
        )
    
    async def close(self):
        """Close connections"""
        await self.jupiter.close()
        if self.rpc:
            await self.rpc.close()


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        swap = JupiterSwap()
        
        # Test quote (0.1 SOL -> USDC)
        quote = await swap.get_quote(
            JupiterSwap.SOL,
            JupiterSwap.USDC,
            0.1
        )
        
        if quote:
            print(f"\nQuote: 0.1 SOL -> {quote.out_amount / 1e6:.2f} USDC")
            print(f"Price Impact: {quote.price_impact:.4f}%")
        
        # Test dry run buy
        result = await swap.buy_token(
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
            0.01  # 0.01 SOL
        )
        
        print(f"\nDry Run Result:")
        print(f"  Success: {result.success}")
        print(f"  Input: {result.input_amount} SOL")
        print(f"  Output: {result.output_amount}")
        print(f"  Note: {result.error}")
        
        await swap.close()
    
    asyncio.run(test())
