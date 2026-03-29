"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                      NEXUS AI - RugCheck.xyz Client                            ║
║            Security Analysis GRATUITA - Sostituisce Birdeye Security!          ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import httpx
from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class RugCheckResult:
    """Security analysis from RugCheck.xyz"""
    token_address: str
    token_name: str
    token_symbol: str
    
    # Security score (higher = safer, typically 0-15000+)
    score: int
    score_normalized: int  # 0-100 for easy comparison
    
    # Risks
    risks: list  # List of {name, description, level, score}
    risk_count: int
    danger_count: int  # "danger" level risks
    warn_count: int    # "warn" level risks
    
    # Authorities
    mint_authority: bool  # True = CAN mint new tokens (BAD!)
    freeze_authority: bool  # True = CAN freeze accounts (BAD!)
    mutable_metadata: bool  # True = can change token info
    
    # Holders
    top_10_holders_pct: float
    top_holder_pct: float
    holder_count: int
    
    # LP
    lp_locked_pct: float
    lp_providers: int
    
    # Creator
    creator: str
    
    @property
    def is_safe(self) -> bool:
        """Quick safety check"""
        return (
            not self.mint_authority and 
            not self.freeze_authority and 
            self.danger_count == 0 and
            self.top_holder_pct < 30
        )
    
    @property
    def safety_emoji(self) -> str:
        if self.danger_count > 0:
            return "🔴"
        elif self.warn_count > 0:
            return "🟡"
        else:
            return "🟢"


class RugCheckClient:
    """
    RugCheck.xyz API Client
    
    FREE - No API key needed!
    Provides comprehensive security analysis for Solana tokens.
    """
    
    BASE_URL = "https://api.rugcheck.xyz/v1"
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15.0,
            headers={"Accept": "application/json"}
        )
        self._cache = {}
        logger.info("🔐 RugCheck.xyz client initialized (FREE!)")
    
    async def check_token(self, mint: str) -> Optional[RugCheckResult]:
        """
        Get comprehensive security report for a token
        
        Args:
            mint: Token mint address
            
        Returns:
            RugCheckResult with all security data
        """
        # Check cache (reports don't change often)
        if mint in self._cache:
            return self._cache[mint]
        
        try:
            url = f"{self.BASE_URL}/tokens/{mint}/report"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Parse risks
            risks = data.get("risks", [])
            danger_count = sum(1 for r in risks if r.get("level") == "danger")
            warn_count = sum(1 for r in risks if r.get("level") == "warn")
            
            # Parse holders
            top_holders = data.get("topHolders", [])
            top_10_pct = sum(float(h.get("pct", 0)) for h in top_holders[:10])
            top_holder_pct = float(top_holders[0].get("pct", 0)) if top_holders else 0
            
            # Parse token info
            token = data.get("token", {})
            token_meta = data.get("tokenMeta", {})
            
            # Parse markets/LP
            markets = data.get("markets", [])
            total_lp_locked = sum(
                float(m.get("lp", {}).get("lpLockedPct", 0) or 0) 
                for m in markets
            )
            lp_providers = sum(
                int(m.get("lp", {}).get("lpProviders", 0) or 0) 
                for m in markets
            )
            
            # Normalize score to 0-100
            raw_score = data.get("score", 0)
            # RugCheck scores are typically 0-15000+, higher = safer
            normalized = min(100, raw_score / 150)  # Rough normalization
            
            result = RugCheckResult(
                token_address=mint,
                token_name=token_meta.get("name", "Unknown"),
                token_symbol=token_meta.get("symbol", "???"),
                
                score=raw_score,
                score_normalized=int(normalized),
                
                risks=risks,
                risk_count=len(risks),
                danger_count=danger_count,
                warn_count=warn_count,
                
                mint_authority=bool(token.get("mintAuthority")),
                freeze_authority=bool(token.get("freezeAuthority")),
                mutable_metadata=bool(token_meta.get("mutable")),
                
                top_10_holders_pct=top_10_pct,
                top_holder_pct=top_holder_pct,
                holder_count=len(top_holders),
                
                lp_locked_pct=total_lp_locked,
                lp_providers=lp_providers,
                
                creator=data.get("creator", "")
            )
            
            # Cache result
            self._cache[mint] = result
            
            logger.debug(f"RugCheck {mint[:8]}: score={raw_score}, dangers={danger_count}")
            return result
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Token {mint[:8]} not found on RugCheck")
            else:
                logger.error(f"RugCheck error: {e}")
            return None
        except Exception as e:
            logger.error(f"RugCheck error: {e}")
            return None
    
    async def get_security_summary(self, mint: str) -> dict:
        """
        Get a summary dict suitable for AI analysis
        
        Returns dict with all security data formatted for LLM
        """
        result = await self.check_token(mint)
        if not result:
            return {"error": "Could not fetch security data"}
        
        return {
            "token": result.token_symbol,
            "security_score": result.score_normalized,
            "is_safe": result.is_safe,
            
            "authorities": {
                "mint_authority": "ACTIVE - CAN MINT!" if result.mint_authority else "Revoked ✓",
                "freeze_authority": "ACTIVE - CAN FREEZE!" if result.freeze_authority else "Revoked ✓",
                "mutable_metadata": "Yes" if result.mutable_metadata else "No ✓"
            },
            
            "risks": {
                "total": result.risk_count,
                "danger_level": result.danger_count,
                "warning_level": result.warn_count,
                "details": [
                    f"{r.get('level').upper()}: {r.get('name')}" 
                    for r in result.risks[:5]
                ]
            },
            
            "holders": {
                "top_holder_pct": f"{result.top_holder_pct:.1f}%",
                "top_10_holders_pct": f"{result.top_10_holders_pct:.1f}%",
                "concentration_risk": "HIGH" if result.top_holder_pct > 20 else "MEDIUM" if result.top_holder_pct > 10 else "LOW"
            },
            
            "liquidity": {
                "lp_locked_pct": f"{result.lp_locked_pct:.1f}%",
                "lp_providers": result.lp_providers,
                "lp_risk": "HIGH - NOT LOCKED!" if result.lp_locked_pct < 50 else "LOW"
            },
            
            "verdict": self._get_verdict(result)
        }
    
    def _get_verdict(self, result: RugCheckResult) -> str:
        """Generate AI-friendly verdict"""
        issues = []
        
        if result.mint_authority:
            issues.append("🔴 CRITICAL: Mint authority active - devs can print tokens!")
        if result.freeze_authority:
            issues.append("🔴 CRITICAL: Freeze authority active - can freeze your tokens!")
        if result.danger_count > 0:
            issues.append(f"🔴 {result.danger_count} DANGER-level risks found")
        if result.top_holder_pct > 30:
            issues.append(f"🟡 High concentration: top holder owns {result.top_holder_pct:.1f}%")
        if result.lp_locked_pct < 50:
            issues.append(f"🟡 LP not locked: only {result.lp_locked_pct:.1f}% locked")
        
        if not issues:
            return "✅ SAFE - No major security issues detected"
        else:
            return " | ".join(issues)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        client = RugCheckClient()
        
        # Test with IMU token
        mint = "42pD2SYDktHF5g453Ksg7JhGEVVqJrZPqTudiQ1Xe6st"
        
        print("=" * 60)
        print("   🔐 RUGCHECK.XYZ TEST")
        print("=" * 60)
        
        result = await client.check_token(mint)
        if result:
            print(f"\n📛 Token: {result.token_name} ({result.token_symbol})")
            print(f"🔐 Score: {result.score} (normalized: {result.score_normalized}/100)")
            print(f"✅ Safe: {result.is_safe}")
            
            print(f"\n🔑 AUTHORITIES:")
            print(f"   Mint: {'❌ ACTIVE' if result.mint_authority else '✅ Revoked'}")
            print(f"   Freeze: {'❌ ACTIVE' if result.freeze_authority else '✅ Revoked'}")
            print(f"   Mutable: {'⚠️ Yes' if result.mutable_metadata else '✅ No'}")
            
            print(f"\n⚠️ RISKS: {result.risk_count} total ({result.danger_count} danger, {result.warn_count} warn)")
            for r in result.risks[:3]:
                emoji = "🔴" if r.get("level") == "danger" else "🟡"
                print(f"   {emoji} {r.get('name')}")
            
            print(f"\n👥 HOLDERS:")
            print(f"   Top holder: {result.top_holder_pct:.1f}%")
            print(f"   Top 10: {result.top_10_holders_pct:.1f}%")
            
            print(f"\n💧 LP:")
            print(f"   Locked: {result.lp_locked_pct:.1f}%")
            print(f"   Providers: {result.lp_providers}")
        
        # Test summary for AI
        print("\n" + "=" * 60)
        print("   📊 SUMMARY FOR AI")
        print("=" * 60)
        summary = await client.get_security_summary(mint)
        import json
        print(json.dumps(summary, indent=2))
        
        await client.close()
        print("\n✅ RugCheck.xyz working!")
    
    asyncio.run(test())
