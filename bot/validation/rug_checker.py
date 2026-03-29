"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Rug Checker                               ║
║                      Multi-source rug pull detection                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from dataclasses import dataclass
from loguru import logger
from typing import Optional
from data.birdeye import BirdeyeClient
from data.dexscreener import DexScreenerClient
from data.rugcheck import RugCheckClient


@dataclass
class RugCheckResult:
    """Complete rug check result"""
    mint: str
    symbol: str
    is_safe: bool
    safety_score: int  # 0-100
    
    # Checks
    liquidity_ok: bool
    holders_ok: bool
    ownership_ok: bool
    contract_ok: bool
    age_ok: bool
    
    # Details
    liquidity_usd: float
    holder_count: int
    top_holder_percent: float
    has_freeze: bool
    has_mint: bool
    age_hours: float
    
    # Flags
    red_flags: list[str]
    warnings: list[str]
    
    def __str__(self) -> str:
        status = "✅ SAFE" if self.is_safe else "❌ RISKY"
        return f"{self.symbol}: {status} (Score: {self.safety_score}/100)"


class RugChecker:
    """
    Multi-source rug pull checker
    
    Checks:
    1. Liquidity (min threshold)
    2. Holder distribution
    3. Ownership/authorities
    4. Contract safety
    5. Token age
    """
    
    # Thresholds
    MIN_LIQUIDITY_USD = 15_000  # Lowered for early memecoins (safety via other checks)
    MIN_HOLDERS = 50
    MAX_TOP_HOLDER_PERCENT = 25
    MAX_TOP_10_PERCENT = 55
    MIN_AGE_HOURS = 0.5
    
    def __init__(
        self,
        *,
        birdeye: Optional[BirdeyeClient] = None,
        dexscreener: Optional[DexScreenerClient] = None,
        rugcheck: Optional[RugCheckClient] = None,
        requester=None
    ):
        self.birdeye = birdeye or BirdeyeClient()
        self.dexscreener = dexscreener or DexScreenerClient()
        self.rugcheck = rugcheck or RugCheckClient()  # PRIMARY - FREE, no rate limits!
        self._requester = requester
        self._own_birdeye = birdeye is None
        self._own_dexscreener = dexscreener is None
        self._own_rugcheck = rugcheck is None
        logger.info("Rug Checker initialized (RugCheck.xyz primary)")

    async def _call(self, api_name: str, func, *args, **kwargs):
        if self._requester:
            return await self._requester(api_name, func, *args, **kwargs)
        return await func(*args, **kwargs)
    
    async def check(self, mint: str, scan_liquidity: float = 0) -> Optional[RugCheckResult]:
        """
        Run complete rug check - Uses RugCheck.xyz + DexScreener (no rate limits!)
        
        Args:
            mint: Token mint address
            scan_liquidity: Fallback liquidity from scanner (GeckoTerminal/PumpFun)
            
        Returns:
            RugCheckResult or None
        """
        logger.info(f"🔍 Running rug check for {mint[:8]}...")
        
        red_flags = []
        warnings = []
        
        # ════════════════════════════════════════════════════════════════════
        # PRIMARY: RugCheck.xyz (FREE, no rate limits!)
        # ════════════════════════════════════════════════════════════════════
        rugcheck_data = await self._call("rugcheck", self.rugcheck.check_token, mint)
        
        # SECONDARY: DexScreener (FREE, no rate limits)
        pairs = await self._call("dexscreener", self.dexscreener.get_token_pairs, mint)
        
        # Get best pair for liquidity/age
        best_pair = None
        if pairs:
            best_pair = max(pairs, key=lambda p: p.liquidity_usd)
        
        # If no data at all, fail
        if not rugcheck_data and not pairs:
            logger.warning("Could not fetch token data from any source")
            return None
        
        # ════════════════════════════════════════════════════════════════════
        #                         RUN CHECKS
        # ════════════════════════════════════════════════════════════════════
        
        # 1. Liquidity Check - Use DexScreener, fallback to scan data
        liquidity = best_pair.liquidity_usd if best_pair else scan_liquidity
        liquidity_ok = liquidity >= self.MIN_LIQUIDITY_USD
        if not liquidity_ok:
            red_flags.append(f"Low liquidity: ${liquidity:,.0f}")
        
        # 2. Holders Check - Use RugCheck.xyz data
        holder_count = rugcheck_data.holder_count if rugcheck_data else 100
        holders_ok = holder_count >= self.MIN_HOLDERS
        if rugcheck_data and not holders_ok:
            if holder_count < 50:
                red_flags.append(f"Very few holders: {holder_count}")
            else:
                warnings.append(f"Low holder count: {holder_count}")
        
        # 3. Ownership Check - Use RugCheck.xyz data
        top_holder_percent = rugcheck_data.top_holder_pct if rugcheck_data else 0
        top_10_percent = rugcheck_data.top_10_holders_pct if rugcheck_data else 0
        
        ownership_ok = (
            top_holder_percent < self.MAX_TOP_HOLDER_PERCENT and
            top_10_percent < self.MAX_TOP_10_PERCENT
        )
        
        if top_holder_percent >= self.MAX_TOP_HOLDER_PERCENT:
            red_flags.append(f"Top holder owns {top_holder_percent:.1f}%")
        if top_10_percent >= self.MAX_TOP_10_PERCENT:
            warnings.append(f"Top 10 own {top_10_percent:.1f}%")
        
        # 4. Contract Check - Use RugCheck.xyz data (BEST SOURCE!)
        has_freeze = rugcheck_data.freeze_authority if rugcheck_data else False
        has_mint = rugcheck_data.mint_authority if rugcheck_data else False
        
        contract_ok = not has_freeze and not has_mint
        
        if has_mint:
            red_flags.append("⚠️ MINT AUTHORITY ENABLED - Can print tokens!")
        if has_freeze:
            red_flags.append("⚠️ FREEZE AUTHORITY ENABLED - Can freeze your tokens!")
        
        # 5. RugCheck.xyz Risks
        if rugcheck_data:
            for risk in rugcheck_data.risks:
                if risk.get("level") == "danger":
                    red_flags.append(f"🔴 {risk.get('name')}")
                elif risk.get("level") == "warn":
                    warnings.append(f"🟡 {risk.get('name')}")
        
        # 6. Age Check
        age_hours = 0
        if best_pair and best_pair.pair_created_at:
            age_hours = best_pair.age_hours
        
        age_ok = age_hours >= self.MIN_AGE_HOURS
        if age_hours < 0.5:
            warnings.append(f"Very new token: {age_hours*60:.0f} minutes old")
        
        # ════════════════════════════════════════════════════════════════════
        #                       CALCULATE SCORE
        # ════════════════════════════════════════════════════════════════════
        
        # Use RugCheck score as base if available
        if rugcheck_data:
            score = rugcheck_data.score_normalized
        else:
            score = 100
        
        # Major penalties
        if has_mint:
            score -= 40
        if has_freeze:
            score -= 30
        if not liquidity_ok:
            score -= 25
        if top_holder_percent >= 30:
            score -= 20
        
        # Minor penalties
        if not holders_ok:
            score -= 10
        if top_10_percent >= 40:
            score -= 10
        if age_hours < 1:
            score -= 5
        
        score = max(0, min(100, score))
        
        # Is it safe? 
        # ═══════════════════════════════════════════════════════════════════
        # SIMULATION MODE: Be more lenient for memecoins!
        # Critical: NO mint authority (can print tokens = rug)
        # Acceptable: Freeze authority (common on Pump.fun, usually disabled)
        # ═══════════════════════════════════════════════════════════════════
        is_safe = (
            score >= 30 and              # Lowered from 50 for memecoins
            not has_mint and             # CRITICAL: No mint authority
            liquidity_ok                 # Must have liquidity
            # Removed freeze check - common on Pump.fun graduated tokens
        )
        
        # Debug: log why tokens fail
        if not is_safe:
            reasons = []
            if score < 30:
                reasons.append(f"score {score}<30")
            if has_mint:
                reasons.append("has_mint_authority")
            if not liquidity_ok:
                reasons.append(f"liq ${liquidity:,.0f}<${self.MIN_LIQUIDITY_USD:,.0f}")
            logger.debug(f"   ❌ Fail reasons: {', '.join(reasons)}")
        
        # Get symbol from available sources
        symbol = "???"
        if rugcheck_data and rugcheck_data.token_symbol:
            symbol = rugcheck_data.token_symbol
        elif best_pair:
            symbol = best_pair.base_symbol
        
        result = RugCheckResult(
            mint=mint,
            symbol=symbol,
            is_safe=is_safe,
            safety_score=score,
            liquidity_ok=liquidity_ok,
            holders_ok=holders_ok,
            ownership_ok=ownership_ok,
            contract_ok=contract_ok,
            age_ok=age_ok,
            liquidity_usd=liquidity,
            holder_count=holder_count,
            top_holder_percent=top_holder_percent,
            has_freeze=has_freeze,
            has_mint=has_mint,
            age_hours=age_hours,
            red_flags=red_flags,
            warnings=warnings
        )
        
        logger.info(str(result))
        return result
    
    async def quick_check(self, mint: str) -> bool:
        """
        Quick pass/fail check
        
        Args:
            mint: Token mint address
            
        Returns:
            True if safe, False if risky
        """
        result = await self.check(mint)
        return result.is_safe if result else False
    
    async def close(self):
        """Close HTTP clients"""
        if self._own_birdeye:
            await self.birdeye.close()
        if self._own_dexscreener:
            await self.dexscreener.close()

        if self._own_rugcheck:
            await self.rugcheck.close()


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        checker = RugChecker()
        
        # Test with BONK (should be safe)
        bonk = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        result = await checker.check(bonk)
        
        if result:
            print(f"\n{'='*50}")
            print(f"Token: {result.symbol}")
            print(f"Safe: {result.is_safe}")
            print(f"Score: {result.safety_score}/100")
            print(f"\nChecks:")
            print(f"  Liquidity: {'✅' if result.liquidity_ok else '❌'} ${result.liquidity_usd:,.0f}")
            print(f"  Holders: {'✅' if result.holders_ok else '❌'} {result.holder_count:,}")
            print(f"  Ownership: {'✅' if result.ownership_ok else '❌'} Top: {result.top_holder_percent:.1f}%")
            print(f"  Contract: {'✅' if result.contract_ok else '❌'}")
            print(f"  Age: {'✅' if result.age_ok else '❌'} {result.age_hours:.1f}h")
            
            if result.red_flags:
                print(f"\n🚩 Red Flags:")
                for flag in result.red_flags:
                    print(f"  - {flag}")
            
            if result.warnings:
                print(f"\n⚠️ Warnings:")
                for warn in result.warnings:
                    print(f"  - {warn}")
        
        await checker.close()
    
    asyncio.run(test())
