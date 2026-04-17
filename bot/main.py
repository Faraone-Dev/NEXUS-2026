"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - SOLANA EDITION                            ║
║                              Main Entry Point                                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝

                    🚀 AI-Powered Solana Trading Bot 🚀
                    
                    Multi-Agent System:
                    • Token Analyzer
                    • Sentiment Analyzer  
                    • Risk Assessor
                    • Master Decision

"""

import sys
import signal
import asyncio
import json
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Set
from loguru import logger

from config import config, Config

# ═══════════════════════════════════════════════════════════════════════════════
#                         CORE INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════
from core import (
    rate_limiter,
    RateLimitConfig,
    health_monitor,
    CircuitConfig,
    resilient_client,
    AsyncOptimizer
)
from security import security_scanner, token_checker
from ai.engine import AIEngine
from ai.agents import Decision
from ai.learning import LearningEngine
from ai.reactive import ReactiveAI, TradeOutcome
from data.jupiter import JupiterClient
from data.birdeye import BirdeyeClient
from data.dexscreener import DexScreenerClient
from data.helius import HeliusClient
from data.pumpfun import PumpFunClient
from data.database import Database, TradeRecord, TokenScan
from data.whale_tracker import WhaleTracker
from data.scan_updater import ScanUpdater
from data.aarna_signals import AarnaSignalClient
from validation.rug_checker import RugChecker
from execution.jupiter_swap import JupiterSwap
from execution.position_manager import PositionManager
from execution.simulator import TradeSimulator
from telegram.alerts import AlertManager


# ═══════════════════════════════════════════════════════════════════════════════
#                              LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════════

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    level=config.LOG_LEVEL
)
logger.add(
    "logs/nexus_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG"
)


# ═══════════════════════════════════════════════════════════════════════════════
#                              NEXUS BOT
# ═══════════════════════════════════════════════════════════════════════════════

class NexusBot:
    """
    Main NEXUS AI Trading Bot
    
    Pipeline:
    1. Scan for new tokens (Helius/DexScreener/Birdeye)
    2. Filter by criteria
    3. Run rug check
    4. AI multi-agent analysis
    5. Execute trades
    6. Manage positions
    
    Infrastructure:
    - Rate limiting (Token Bucket + Exponential Backoff)
    - Circuit breaker (Auto-recovery from failures)
    - Health monitoring (Real-time API status)
    - Fallback chains (Redundant data sources)
    """
    
    def __init__(self):
        # ═══════════════════════════════════════════════════════════════════
        # INFRASTRUCTURE SETUP (Rate Limiting + Circuit Breaker)
        # ═══════════════════════════════════════════════════════════════════
        self._setup_infrastructure()
        
        # Components
        self.db = Database()
        self.ai = AIEngine()
        self.learning = LearningEngine(self.db)
        self.reactive = ReactiveAI()  # Real-time learning
        self.pumpfun = PumpFunClient()  # PRIMARY - hottest tokens, FREE!
        self.helius = HeliusClient()  # No rate limits
        self.birdeye = BirdeyeClient()
        self.dexscreener = DexScreenerClient()
        self.whale_tracker = WhaleTracker()
        self.aarna = AarnaSignalClient()  # MCP TA signals
        self.scan_updater = ScanUpdater(self.db, requester=self._rate_limited_call)
        self.rug_checker = RugChecker(
            birdeye=self.birdeye,
            dexscreener=self.dexscreener,
            requester=self._rate_limited_call
        )
        self.swap = JupiterSwap()
        self.positions = PositionManager()
        self.alerts = AlertManager()
        
        # SIMULATION MODE - Paper trading con dati reali
        self.simulation_mode = config.SIMULATION_MODE
        self.simulator = None
        if self.simulation_mode:
            self.simulator = TradeSimulator(
                starting_balance=config.SIMULATION_STARTING_SOL,
                max_positions=config.MAX_POSITIONS
            )
            logger.info("📊 SIMULATION MODE ACTIVE - No real trades!")
            
            # ═══════════════════════════════════════════════════════════════════
            # SYNC: Restore saved positions into simulator
            # ═══════════════════════════════════════════════════════════════════
            for pos in self.positions.get_all_positions():
                from execution.simulator import SimulatedPosition
                from datetime import datetime
                
                entry_time = datetime.now()
                if pos.entry_time:
                    try:
                        entry_time = datetime.fromisoformat(pos.entry_time) if isinstance(pos.entry_time, str) else pos.entry_time
                    except:
                        pass
                
                # Note: pos.stop_loss/take_profit are PRICE values, not percentages!
                # Use config values for SL/TP percentages
                sim_pos = SimulatedPosition(
                    token_address=pos.token_mint,
                    token_symbol=pos.token_symbol,
                    entry_price=pos.entry_price,
                    entry_time=entry_time,
                    amount_sol=pos.sol_invested,
                    token_amount=pos.amount,
                    stop_loss=config.STOP_LOSS_PERCENT / 100,    # 15% -> 0.15
                    take_profit=config.TAKE_PROFIT_PERCENT / 100, # 50% -> 0.50
                    current_price=pos.current_price or pos.entry_price
                )
                self.simulator.positions[pos.token_mint] = sim_pos
                self.simulator.stats.current_balance -= pos.sol_invested
                
            if self.simulator.positions:
                logger.info(f"📊 Restored {len(self.simulator.positions)} positions into simulator")
        
        # State
        self.running = False
        self.tokens_analyzed = 0
        self.trades_executed = 0
        
        # COOLDOWN: Track tokens we lost on to avoid re-entry
        self.token_cooldown = {}  # {token_address: cooldown_until_timestamp}
        self.COOLDOWN_MINUTES = 5  # Don't re-enter same token for 5 minutes after loss

        # Concurrency helpers
        self.trade_lock = asyncio.Lock()
        self.pair_cache: Dict[str, dict] = {}
        self.PAIR_CACHE_TTL = 60  # seconds
        scan_interval = getattr(config, "SCAN_INTERVAL", 30) or 30
        self.SCAN_CACHE_TTL = max(5, int(scan_interval / 2))
        self.scan_refresh_interval = max(10, int(scan_interval / 2))
        self.scan_cache = {"timestamp": 0.0, "tokens": [], "meta": {}}
        self.scan_cache_lock = asyncio.Lock()
        self.SCAN_CONCURRENCY = 3
        self._scan_refresher_task: Optional[asyncio.Task] = None
        self.known_mints: Set[str] = set()
        
        # Infrastructure stats
        self.api_errors = 0
        self.rate_limited_calls = 0
        
        logger.info("NEXUS Bot initialized with resilient infrastructure")

    # ─── A/B log persistence (dashboard) ─────────────────────
    _AB_LOG_PATH = Path(__file__).parent / "data_store" / "ab_log.json"
    _AB_MAX_ENTRIES = 500

    def _append_ab_log(self, entry: dict):
        """Append an A/B comparison entry to data_store/ab_log.json."""
        try:
            data = json.loads(self._AB_LOG_PATH.read_text()) if self._AB_LOG_PATH.exists() else []
        except Exception:
            data = []
        data.append(entry)
        if len(data) > self._AB_MAX_ENTRIES:
            data = data[-self._AB_MAX_ENTRIES:]
        self._AB_LOG_PATH.write_text(json.dumps(data, indent=2))

    # ─── Activity log persistence (dashboard) ────────────────
    _ACTIVITY_PATH = Path(__file__).parent / "data_store" / "activity.json"
    _ACTIVITY_MAX = 500

    def _log_activity(self, event_type: str, message: str, pnl=None):
        """Append an activity event for the dashboard."""
        try:
            data = json.loads(self._ACTIVITY_PATH.read_text()) if self._ACTIVITY_PATH.exists() else []
        except Exception:
            data = []
        entry = {
            "type": event_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        if pnl is not None:
            entry["pnl"] = pnl
        data.append(entry)
        if len(data) > self._ACTIVITY_MAX:
            data = data[-self._ACTIVITY_MAX:]
        self._ACTIVITY_PATH.write_text(json.dumps(data, indent=2))

    def _setup_infrastructure(self):
        """
        Initialize rate limiting and circuit breaker for all APIs
        
        This provides:
        - Protection against API rate limits
        - Automatic recovery from failures
        - Health monitoring for all data sources
        """
        # Configure rate limits per API
        api_configs = {
            "jupiter": RateLimitConfig(requests_per_second=10, burst_size=20, max_retries=3),
            "birdeye": RateLimitConfig(requests_per_second=5, burst_size=10, max_retries=3),
            "dexscreener": RateLimitConfig(requests_per_second=5, burst_size=15, max_retries=3),
            "helius": RateLimitConfig(requests_per_second=10, burst_size=30, max_retries=3),
            "rugcheck": RateLimitConfig(requests_per_second=2, burst_size=5, max_retries=5),
            "pumpfun": RateLimitConfig(requests_per_second=5, burst_size=10, max_retries=3),
            "deepseek": RateLimitConfig(requests_per_second=2, burst_size=5, max_retries=3),
        }
        
        for api_name, config in api_configs.items():
            rate_limiter.configure(api_name, config)
            health_monitor.register(api_name, CircuitConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout=30.0
            ))
        
        logger.info("Infrastructure configured: Rate limiting + Circuit breakers")
    
    async def _rate_limited_call(self, api_name: str, func, *args, **kwargs):
        """
        Execute API call with rate limiting and circuit breaker
        
        Automatically handles:
        - Rate limiting (waits if needed)
        - Circuit breaker (fails fast if API is down)
        - Retries with exponential backoff
        - Health monitoring
        """
        start = time.time()
        circuit = health_monitor.get_circuit(api_name)
        
        # Check circuit breaker
        if not await circuit.can_execute():
            logger.warning(f"⚡ {api_name} circuit OPEN - skipping call")
            self.api_errors += 1
            return None
        
        try:
            result = await rate_limiter.execute_with_retry(
                api_name,
                lambda: func(*args, **kwargs)
            )
            
            # Record success
            latency = (time.time() - start) * 1000
            await health_monitor.record_call(api_name, True, latency)
            
            return result
            
        except Exception as e:
            # Record failure
            latency = (time.time() - start) * 1000
            await health_monitor.record_call(api_name, False, latency, e)
            
            if "429" in str(e) or "rate" in str(e).lower():
                self.rate_limited_calls += 1
                logger.warning(f"⏳ {api_name} rate limited")
            else:
                self.api_errors += 1
                logger.debug(f"{api_name} error: {e}")
            
            return None
    
    def get_api_health_status(self) -> dict:
        """
        Get current health status of all APIs
        
        Returns dict with API health info for dashboard/monitoring
        """
        health = health_monitor.get_health()
        stats = rate_limiter.get_stats()
        
        status = {
            "all_healthy": health_monitor.get_all_healthy(),
            "unhealthy": health_monitor.get_unhealthy(),
            "total_errors": self.api_errors,
            "rate_limited": self.rate_limited_calls,
            "apis": {}
        }
        
        for api_name in ["jupiter", "birdeye", "dexscreener", "helius", "rugcheck", "pumpfun"]:
            h = health.get(api_name)
            s = stats.get(api_name)
            
            if h:
                status["apis"][api_name] = {
                    "healthy": h.is_healthy,
                    "circuit": h.circuit_state.value,
                    "success_rate": f"{h.success_rate:.0%}",
                    "latency_ms": f"{h.latency_avg_ms:.0f}",
                    "requests": s.total_requests if s else 0
                }
        
        return status
    
    async def _fetch_pumpfun_tokens(self, limit: int = 20) -> list[dict]:
        """Fetch tokens from Pump.fun/GeckoTerminal with volume filter."""
        tokens = []
        try:
            pump_tokens = await self._rate_limited_call(
                "pumpfun",
                self.pumpfun.get_pumpswap_tokens,
                limit=limit
            ) or []

            for token in pump_tokens:
                addr = token.mint
                if not addr:
                    continue
                if token.volume_24h < 5000:
                    continue
                if token.liquidity_usd < config.MIN_LIQUIDITY_USD:
                    continue
                tokens.append({
                    "mint": addr,
                    "symbol": token.symbol,
                    "name": token.name,
                    "liquidity": token.liquidity_usd,
                    "price": token.price_usd,
                    "market_cap": token.fdv,
                    "volume_24h": token.volume_24h,
                    "price_change_24h": token.price_change_24h,
                    "buys_24h": token.buys_24h,
                    "sells_24h": token.sells_24h,
                    "age_hours": token.age_hours,
                    "source": "pumpfun"
                })
        except Exception as e:
            logger.debug(f"GeckoTerminal/PumpSwap scan: {e}")
        return tokens

    async def _fetch_dexscreener_tokens(self, limit: int = 30) -> list[dict]:
        """Fetch trending tokens from DexScreener."""
        tokens = []
        try:
            dex_tokens = await self._rate_limited_call(
                "dexscreener",
                self.dexscreener.get_trending_tokens,
                limit=limit
            ) or []

            for token in dex_tokens:
                addr = token.get("address")
                if not addr:
                    continue
                liquidity = float(token.get("liquidity", 0) or 0)
                if liquidity < config.MIN_LIQUIDITY_USD:
                    continue
                tokens.append({
                    "mint": addr,
                    "symbol": token.get("symbol"),
                    "name": token.get("name"),
                    "liquidity": liquidity,
                    "price": float(token.get("price", 0) or 0),
                    "source": "dexscreener"
                })
        except Exception as e:
            logger.debug(f"DexScreener scan error: {e}")
        return tokens

    async def _fetch_birdeye_tokens(self, limit: int = 30) -> list[dict]:
        """Fetch recent listings from Birdeye."""
        tokens = []
        try:
            new_tokens = await self._rate_limited_call(
                "birdeye",
                self.birdeye.get_new_listings,
                limit=limit
            ) or []

            for token in new_tokens:
                addr = token.get("address")
                if not addr:
                    continue
                liquidity = float(token.get("liquidity", 0) or 0)
                if liquidity < config.MIN_LIQUIDITY_USD:
                    continue
                tokens.append({
                    "mint": addr,
                    "symbol": token.get("symbol"),
                    "name": token.get("name"),
                    "liquidity": liquidity,
                    "price": float(token.get("price", 0) or 0),
                    "source": "birdeye"
                })
        except Exception as e:
            logger.debug(f"Birdeye scan error: {e}")
        return tokens

    async def _collect_scan_candidates(self) -> list[dict]:
        """Fetch raw token candidates from all sources."""
        pump_task = self._fetch_pumpfun_tokens()
        dex_task = self._fetch_dexscreener_tokens()

        pump_tokens, dex_tokens = await AsyncOptimizer.gather_with_concurrency(
            [pump_task, dex_task],
            max_concurrent=2
        )

        tokens = []
        seen_addresses = set()

        for collection in (pump_tokens, dex_tokens):
            for token in collection:
                addr = token.get("mint")
                if addr and addr not in seen_addresses:
                    tokens.append(token)
                    seen_addresses.add(addr)

        if len(tokens) < 5:
            birdeye_tokens = await self._fetch_birdeye_tokens()
            for token in birdeye_tokens:
                addr = token.get("mint")
                if addr and addr not in seen_addresses:
                    tokens.append(token)
                    seen_addresses.add(addr)

        return tokens

    async def _collect_known_mints(self) -> Set[str]:
        """Gather mints already handled to avoid re-scanning."""
        known = {pos.token_mint for pos in self.positions.get_all_positions()}
        if self.simulator and self.simulator.positions:
            known.update(self.simulator.positions.keys())

        try:
            recent_mints = await asyncio.to_thread(self.db.get_seen_token_mints, 500)
            if recent_mints:
                known.update(recent_mints)
        except Exception as exc:
            logger.debug(f"Failed to load known mints: {exc}")

        if self.known_mints:
            self.known_mints.clear()
            self.known_mints.update(known)
        else:
            self.known_mints = set(known)
        return set(self.known_mints)

    async def _update_scan_cache(self, *, force: bool = False):
        """Refresh cached scan results when stale or on demand."""
        async with self.scan_cache_lock:
            now = time.time()
            cache_timestamp = self.scan_cache.get("timestamp", 0.0)
            if not force and now - cache_timestamp < self.SCAN_CACHE_TTL:
                return

            candidates = await self._collect_scan_candidates()
            known_mints = await self._collect_known_mints()
            filtered = [token for token in candidates if token.get("mint") not in known_mints]

            pump_count = sum(1 for t in filtered if t['source'] == 'pumpfun')
            dex_count = sum(1 for t in filtered if t['source'] == 'dexscreener')
            bird_count = sum(1 for t in filtered if t['source'] == 'birdeye')

            self.scan_cache = {
                "timestamp": now,
                "tokens": [token.copy() for token in filtered],
                "meta": {
                    "pump": pump_count,
                    "dex": dex_count,
                    "birdeye": bird_count,
                    "total": len(filtered)
                }
            }

    async def _ensure_scan_cache(self):
        """Make sure cached scan data is available."""
        await self._update_scan_cache()

    async def _scan_refresh_loop(self):
        """Background refresher keeping scan cache warm."""
        while self.running:
            try:
                await self._update_scan_cache(force=True)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug(f"Scan refresher error: {exc}")
            await asyncio.sleep(self.scan_refresh_interval)

    async def scan_tokens(self) -> list[dict]:
        """
        Scan for potential tokens from cached data refreshed in background.
        """
        logger.info("🔍 Scanning for tokens...")
        await self._ensure_scan_cache()

        tokens = self.scan_cache.get("tokens", [])
        meta = self.scan_cache.get("meta", {})
        logger.info(
            f"   Found {meta.get('total', len(tokens))} tokens (Pump.fun: {meta.get('pump', 0)}, "
            f"DexScreener: {meta.get('dex', 0)}, Birdeye: {meta.get('birdeye', 0)})"
        )

        return [token.copy() for token in tokens]
    
    async def analyze_token(self, token: dict, rug_result=None) -> dict:
        """
        Get COMPLETE token data for AI analysis.
        Collects ALL available data from multiple sources.
        
        Sources:
        - DexScreener: Price, volume, txns, age
        - RugCheck.xyz: Security score, risks, authorities, holders
        - GeckoTerminal: Volume trends (from token scan)
        """
        import asyncio
        mint = token["mint"]
        
        # PARALLEL API calls for speed
        now = time.time()
        cache_entry = self.pair_cache.get(mint)
        cached_pairs = None
        cached_rugcheck = None
        if cache_entry and now - cache_entry.get("timestamp", 0) < self.PAIR_CACHE_TTL:
            cached_pairs = cache_entry.get("pairs")
            cached_rugcheck = cache_entry.get("rugcheck")
        elif cache_entry:
            self.pair_cache.pop(mint, None)

        need_pairs_fetch = cached_pairs is None
        need_rug_fetch = rug_result is None and cached_rugcheck is None

        pair_task = (
            self._rate_limited_call("dexscreener", self.dexscreener.get_token_pairs, mint)
            if need_pairs_fetch else
            asyncio.sleep(0, result=cached_pairs)
        )

        rug_base = rug_result if rug_result is not None else cached_rugcheck
        rug_task = (
            self.rug_checker.check(mint)
            if need_rug_fetch else
            asyncio.sleep(0, result=rug_base)
        )

        try:
            pair_result, rug_result_val = await asyncio.wait_for(
                asyncio.gather(pair_task, rug_task, return_exceptions=True),
                timeout=8.0
            )
        except asyncio.TimeoutError:
            pair_result, rug_result_val = TimeoutError(), TimeoutError()

        fresh_pairs = None
        if need_pairs_fetch and not isinstance(pair_result, Exception):
            fresh_pairs = pair_result

        fresh_rug = None
        if need_rug_fetch and not isinstance(rug_result_val, Exception):
            fresh_rug = rug_result_val

        if not need_pairs_fetch and cached_pairs is not None:
            pairs = cached_pairs
        elif fresh_pairs is not None:
            pairs = fresh_pairs
        else:
            pairs = []

        if rug_result is not None:
            rugcheck = rug_result
        elif not need_rug_fetch and cached_rugcheck is not None:
            rugcheck = cached_rugcheck
        else:
            rugcheck = fresh_rug

        cache_payload = dict(cache_entry) if cache_entry else {}
        if fresh_pairs is not None:
            cache_payload["pairs"] = fresh_pairs
            cache_payload["timestamp"] = now
        elif not need_pairs_fetch and cached_pairs is not None:
            cache_payload.setdefault("timestamp", now)

        if fresh_rug is not None:
            cache_payload["rugcheck"] = fresh_rug
            cache_payload["timestamp"] = now
        elif not need_rug_fetch and cached_rugcheck is not None:
            cache_payload.setdefault("timestamp", now)

        if cache_payload:
            self.pair_cache[mint] = cache_payload
        
        # Best pair for market data
        best_pair = pairs[0] if pairs else None
        age_hours = best_pair.age_hours if best_pair else 999
        
        # Get txns data if available
        buys_24h = 0
        sells_24h = 0
        if best_pair and hasattr(best_pair, 'txns'):
            txns = best_pair.txns or {}
            if 'h24' in txns:
                buys_24h = txns['h24'].get('buys', 0)
                sells_24h = txns['h24'].get('sells', 0)
        
        # Use data from token scan if available (from GeckoTerminal)
        if token.get("source") == "pumpfun":
            buys_24h = token.get("buys_24h", buys_24h)
            sells_24h = token.get("sells_24h", sells_24h)
        
        # Build COMPREHENSIVE data dict for AI
        data = {
            "mint": mint,
            "symbol": token.get("symbol") or (best_pair.base_symbol if best_pair else "???"),
            "name": token.get("name", "Unknown"),
            "source": token.get("source", "unknown"),
            
            # ═══════════════════════════════════════════════════════════════
            # MARKET DATA (DexScreener)
            # ═══════════════════════════════════════════════════════════════
            "price": best_pair.price_usd if best_pair else token.get("price", 0),
            "liquidity": best_pair.liquidity_usd if best_pair else token.get("liquidity", 0),
            "market_cap": best_pair.fdv if best_pair else token.get("market_cap", 0),
            
            # ═══════════════════════════════════════════════════════════════
            # VOLUME & ACTIVITY
            # ═══════════════════════════════════════════════════════════════
            "volume_24h": best_pair.volume_24h if best_pair else token.get("volume_24h", 0),
            "volume_1h": token.get("volume_1h", 0),  # From GeckoTerminal
            "buys_24h": buys_24h,
            "sells_24h": sells_24h,
            
            # ═══════════════════════════════════════════════════════════════
            # PRICE TRENDS
            # ═══════════════════════════════════════════════════════════════
            "price_change_1h": best_pair.price_change_1h if best_pair else token.get("price_change_1h", 0),
            "price_change_6h": best_pair.price_change_6h if best_pair else 0,
            "price_change_24h": best_pair.price_change_24h if best_pair else token.get("price_change_24h", 0),
            "volatility": 0,  # TODO: Calculate from OHLCV
            
            # ═══════════════════════════════════════════════════════════════
            # SECURITY (RugCheck.xyz - BEST SOURCE!)
            # ═══════════════════════════════════════════════════════════════
            "security_score": rugcheck.score_normalized if rugcheck else 50,
            "has_freeze": rugcheck.freeze_authority if rugcheck else False,
            "has_mint": rugcheck.mint_authority if rugcheck else False,
            "lp_locked_pct": rugcheck.lp_locked_pct if rugcheck else 0,
            "risk_count": rugcheck.risk_count if rugcheck else 0,
            "danger_count": rugcheck.danger_count if rugcheck else 0,
            "warn_count": rugcheck.warn_count if rugcheck else 0,
            "risk_details": ", ".join([f"{r.get('level')}: {r.get('name')}" for r in (rugcheck.risks[:3] if rugcheck else [])]),
            
            # ═══════════════════════════════════════════════════════════════
            # HOLDER DISTRIBUTION (RugCheck.xyz)
            # ═══════════════════════════════════════════════════════════════
            "holder_count": rugcheck.holder_count if rugcheck else 0,
            "top_holder_percent": rugcheck.top_holder_pct if rugcheck else 0,
            "top_10_percent": rugcheck.top_10_holders_pct if rugcheck else 0,
            
            # ═══════════════════════════════════════════════════════════════
            # TOKEN AGE
            # ═══════════════════════════════════════════════════════════════
            "age_hours": age_hours if age_hours < 999 else token.get("age_hours", 999),
            
            # ═══════════════════════════════════════════════════════════════
            # VERIFICATION
            # ═══════════════════════════════════════════════════════════════
            "on_jupiter": False,  # TODO: Check Jupiter verified list
            "verified": False,
        }

        # ═══════════════════════════════════════════════════════════════
        # TECHNICAL ANALYSIS (Aarna MCP - composite signals + indicators)
        # ═══════════════════════════════════════════════════════════════
        try:
            ta_data = await self.aarna.get_signals_for_token(
                data.get("symbol", "")
            )
            if ta_data:
                data.update(ta_data)
                logger.info(f"   📊 TA signals: {ta_data.get('ta_signal', 'N/A')} "
                           f"({ta_data.get('ta_confidence', 0):.0%})")
        except Exception as e:
            logger.debug(f"Aarna TA fetch failed: {e}")

        # ═══════════════════════════════════════════════════════════════
        # SENTIMENT SIGNALS (Whale Tracker + computed metrics)
        # ═══════════════════════════════════════════════════════════════
        # Buy/Sell ratio as market sentiment proxy
        b24 = data.get("buys_24h", 0)
        s24 = data.get("sells_24h", 0)
        data["buy_sell_ratio"] = round(b24 / max(s24, 1), 2)

        # Volume spike detection: 1h volume > 10% of 24h → unusual activity
        v1h = data.get("volume_1h", 0)
        v24h = data.get("volume_24h", 0)
        data["volume_spike"] = v1h > (v24h * 0.10) if v24h > 0 else False

        # Whale flow (Helius API - best-effort, non-blocking)
        try:
            whale_flow = await asyncio.wait_for(
                self.whale_tracker.analyze_token_flow(mint),
                timeout=4.0
            )
            data["whale_buys"] = whale_flow.get("whale_buys", 0)
            data["whale_sells"] = whale_flow.get("whale_sells", 0)
            data["whale_net_flow"] = whale_flow.get("net_flow", 0)
            data["whale_signal"] = whale_flow.get("signal", "NEUTRAL")
            data["whale_notable_wallets"] = whale_flow.get("notable_wallets", [])
            if whale_flow.get("whale_buys", 0) > 0 or whale_flow.get("whale_sells", 0) > 0:
                logger.info(f"   🐋 Whale flow: {whale_flow['signal']} "
                           f"({whale_flow['whale_buys']}B/{whale_flow['whale_sells']}S)")
        except Exception as e:
            logger.debug(f"Whale tracker failed (non-critical): {e}")
            data["whale_buys"] = 0
            data["whale_sells"] = 0
            data["whale_net_flow"] = 0
            data["whale_signal"] = "UNAVAILABLE"
            data["whale_notable_wallets"] = []

        cache_entry_final = self.pair_cache.get(mint, {})
        cache_entry_final["price_snapshot"] = data["price"]
        cache_entry_final.setdefault("timestamp", now)
        self.pair_cache[mint] = cache_entry_final
        
        return data
    
    async def process_token(self, token: dict) -> bool:
        """
        Process a single token through the pipeline
        
        Args:
            token: Token data
            
        Returns:
            True if trade was executed
        """
        mint = token["mint"]
        symbol = token.get("symbol", "???")
        
        logger.info(f"\n{'─'*50}")
        logger.info(f"Processing: {symbol} ({mint[:8]}...)")
        
        # 0. Check COOLDOWN - don't re-enter tokens we just lost on
        import time
        if mint in self.token_cooldown:
            cooldown_until = self.token_cooldown[mint]
            if time.time() < cooldown_until:
                remaining = int((cooldown_until - time.time()) / 60)
                logger.warning(f"   ⏳ COOLDOWN: {symbol} - wait {remaining} more minutes")
                return False
            else:
                # Cooldown expired, remove from dict
                del self.token_cooldown[mint]
        
        # 1. Skip if already in position
        if self.positions.get_position_by_token(mint):
            logger.info(f"   Already in position, skipping")
            return False
        
        # 2. Rug check (quick) - pass scan liquidity as fallback for PumpSwap tokens
        scan_liq = float(token.get("liquidity", 0) or 0)
        rug_result = await self.rug_checker.check(mint, scan_liquidity=scan_liq)
        if not rug_result or not rug_result.is_safe:
            score = getattr(rug_result, 'safety_score', 0) if rug_result else 0
            logger.warning(f"   ❌ Failed rug check")
            self._log_activity("skip", f"{symbol} — rug check FAILED ({score}/100)")
            return False
        
        logger.info(f"   ✅ Rug check: {rug_result.safety_score}/100")
        self._log_activity("scan", f"{symbol} — rug check passed ({rug_result.safety_score}/100), analyzing...")
        
        # 3. Get complete data for AI (PARALLEL - fast)
        full_data = await self.analyze_token(token, rug_result=rug_result)
        
        # 4. AI Analysis - USE FAST MODE for speed!
        decision = await self.ai.fast_analysis(full_data)
        self.tokens_analyzed += 1
        
        if not decision:
            logger.error(f"   AI analysis failed")
            return False
        
        # ──── A/B LOG: rule-based scorer (shadow, never overrides) ────
        from ai.rule_scorer import rule_based_score, RuleDecision
        rule = rule_based_score(full_data)
        llm_dec = decision.decision.value
        agree = (llm_dec == rule.decision)
        tag = "AGREE" if agree else "DISAGREE"
        logger.info(f"   ⚖️ A/B [{tag}] LLM={llm_dec}({decision.confidence}%) "
                     f"RULE={rule.decision}({rule.score}/100)")
        if not agree:
            logger.info(f"      Rule reasons: +[{', '.join(rule.reasons_buy)}] "
                         f"-[{', '.join(rule.reasons_skip)}]")
        # Persist to ab_log.json for dashboard
        self._append_ab_log({
            "symbol": token.get("symbol", token.get("baseToken", {}).get("symbol", "?")),
            "llm_decision": llm_dec,
            "rule_decision": rule.decision,
            "agree": agree,
            "rule_score": rule.score,
            "llm_confidence": decision.confidence,
            "reasons": ", ".join(rule.reasons_buy + rule.reasons_skip),
            "timestamp": datetime.now().isoformat(),
        })
        
        # 5. Learning override check
        should_override, override_reason = self.learning.should_override_ai_decision(
            full_data, decision.decision.value
        )
        if should_override:
            logger.warning(f"   🧠 Learning override: {override_reason}")
            # Record the scan anyway for learning
            await self._record_scan(full_data, "SKIP (learning override)", 0, decision)
            return False
        
        # 5. Check if should trade
        if decision.decision != Decision.BUY:
            logger.info(f"   AI decision: {decision.decision.value} (skip)")
            self._log_activity("skip", f"{symbol} — AI says {decision.decision.value} ({decision.confidence}%)")
            await self._record_scan(full_data, decision.decision.value, decision.confidence, decision)
            return False
        
        if decision.confidence < config.MIN_CONFIDENCE:
            logger.info(f"   Confidence too low: {decision.confidence}% < {config.MIN_CONFIDENCE}%")
            self._log_activity("skip", f"{symbol} — confidence too low ({decision.confidence}% < {config.MIN_CONFIDENCE}%)")
            await self._record_scan(full_data, "SKIP (low confidence)", decision.confidence, decision)
            return False
        
        # 6. Alert signal
        await self.alerts.signal(symbol, decision)
        
        # 7. Execute trade (guarded to avoid concurrent fills)
        async with self.trade_lock:
            if not self.positions.can_open_position():
                logger.warning(f"   Max positions reached ({config.MAX_POSITIONS})")
                return False

            # Calculate SOL amount based on actual balance and config %
            if self.simulation_mode and self.simulator:
                available = self.simulator.stats.current_balance
            else:
                available = config.SIMULATION_STARTING_SOL
            base_sol = available * (config.POSITION_SIZE_PERCENT / 100)
            sol_amount = self.learning.get_adjusted_position_size(base_sol, decision.token_score)

            logger.info(f"   🚀 Executing BUY: {sol_amount:.4f} SOL")

            # ═══════════════════════════════════════════════════════════════════
            # SIMULATION MODE: Use simulator instead of real swap
            # ═══════════════════════════════════════════════════════════════════
            if self.simulation_mode and self.simulator:
                position = self.simulator.open_position(
                    token_address=mint,
                    token_symbol=symbol,
                    current_price=full_data["price"],
                    amount_sol=sol_amount,
                    stop_loss=config.STOP_LOSS_PERCENT,
                    take_profit=config.TAKE_PROFIT_PERCENT
                )

                if position:
                    self.positions.open_position(
                        token_mint=mint,
                        token_symbol=symbol,
                        entry_price=position.entry_price,
                        amount=position.token_amount,
                        sol_invested=sol_amount
                    )

                    await self._record_trade(full_data, decision, sol_amount, position.token_amount, is_simulated=True)

                    await self.alerts.trade_executed(
                        symbol=symbol,
                        side="BUY (SIM)",
                        amount=position.token_amount,
                        price=position.entry_price,
                        sol_amount=sol_amount,
                        signature=f"SIM_{mint[:8]}"
                    )

                    self.trades_executed += 1
                    self._log_activity("buy", f"Bought {symbol} for {sol_amount:.4f} SOL @ ${position.entry_price:.10f}")
                    return True
                return False

            # ═══════════════════════════════════════════════════════════════════
            # REAL MODE: Execute actual swap
            # ═══════════════════════════════════════════════════════════════════
            result = await self.swap.buy_token(mint, sol_amount)

            if result.success:
                self.positions.open_position(
                    token_mint=mint,
                    token_symbol=symbol,
                    entry_price=full_data["price"],
                    amount=result.output_amount,
                    sol_invested=sol_amount
                )

                await self._record_trade(full_data, decision, sol_amount, result.output_amount)

                await self.alerts.trade_executed(
                    symbol=symbol,
                    side="BUY",
                    amount=result.output_amount,
                    price=full_data["price"],
                    sol_amount=sol_amount,
                    signature=result.signature
                )

                self.trades_executed += 1
                return True

            logger.error(f"   Trade failed: {result.error}")
            return False
    
    async def check_positions(self):
        """Check and manage open positions"""
        
        open_positions = self.positions.get_all_positions()
        if not open_positions:
            return
        
        logger.info("📊 Checking positions...")
        
        prices: Dict[str, float] = {}
        to_fetch: list[str] = []
        now = time.time()

        for pos in open_positions:
            mint = pos.token_mint
            cache_entry = self.pair_cache.get(mint)
            if cache_entry and now - cache_entry.get("timestamp", 0) < self.PAIR_CACHE_TTL:
                pairs = cache_entry.get("pairs") or []
                if pairs:
                    prices[mint] = getattr(pairs[0], "price_usd", cache_entry.get("price_snapshot", 0))
                    cache_entry["timestamp"] = now
                    continue
                price_snapshot = cache_entry.get("price_snapshot")
                if price_snapshot is not None:
                    prices[mint] = price_snapshot
                    cache_entry["timestamp"] = now
                    continue
            to_fetch.append(mint)

        async def fetch_pairs(mint: str):
            try:
                pairs = await self._rate_limited_call(
                    "dexscreener",
                    self.dexscreener.get_token_pairs,
                    mint
                ) or []
                return mint, pairs, None
            except Exception as exc:
                return mint, [], exc

        if to_fetch:
            fetch_results = await AsyncOptimizer.gather_with_concurrency(
                [fetch_pairs(m) for m in to_fetch],
                max_concurrent=self.SCAN_CONCURRENCY
            )

            for mint, pairs, error in fetch_results:
                if error:
                    logger.debug(f"Price fetch failed for {mint[:8]}...: {error}")
                    cache_entry = self.pair_cache.get(mint)
                    snapshot = cache_entry.get("price_snapshot") if cache_entry else None
                    if snapshot is not None:
                        prices[mint] = snapshot
                    continue

                price_value = None
                if pairs:
                    price_value = getattr(pairs[0], "price_usd", None)
                    cache_entry = self.pair_cache.get(mint, {})
                    effective_price = price_value if price_value is not None else cache_entry.get("price_snapshot")
                    cache_entry.update({
                        "pairs": pairs,
                        "price_snapshot": effective_price,
                        "timestamp": time.time()
                    })
                    self.pair_cache[mint] = cache_entry
                    price_value = effective_price
                else:
                    cache_entry = self.pair_cache.get(mint)
                    if cache_entry:
                        cache_entry["timestamp"] = time.time()
                        price_value = cache_entry.get("price_snapshot")

                if price_value is not None:
                    prices[mint] = price_value
        
        # ═══════════════════════════════════════════════════════════════════
        # SIMULATION MODE: Update simulator prices and check triggers
        # ═══════════════════════════════════════════════════════════════════
        if self.simulation_mode and self.simulator:
            triggered = self.simulator.update_positions(prices)
            
            for closed_pos in triggered:
                # Find corresponding position in manager
                for pos in self.positions.get_all_positions():
                    if pos.token_mint == closed_pos.token_address:
                        exit_price = closed_pos.exit_price or closed_pos.current_price or pos.current_price
                        if not exit_price and closed_pos.pnl_percent is not None:
                            exit_price = pos.entry_price * (1 + closed_pos.pnl_percent / 100)

                        # Ensure position reflects realised values before learning/close
                        if exit_price:
                            pos.current_price = exit_price
                        pnl_percent_override = closed_pos.pnl_percent
                        if pnl_percent_override is None and exit_price:
                            pnl_percent_override = ((exit_price - pos.entry_price) / pos.entry_price) * 100 if pos.entry_price else 0

                        sol_returned = closed_pos.value_returned_sol
                        if not sol_returned:
                            if closed_pos.pnl_percent is not None:
                                sol_returned = pos.sol_invested + (pos.sol_invested * (closed_pos.pnl_percent / 100))
                            else:
                                sol_returned = pos.sol_invested
                        pnl_sol_override = closed_pos.pnl_sol
                        usd_returned = closed_pos.value_returned_usd
                        logger.debug(
                            f"Simulated close {pos.token_symbol}: {sol_returned:.4f} SOL | ${usd_returned:,.2f}"
                        )
                        if closed_pos.exit_reason == "stop_loss":
                            logger.warning(f"🛑 Stop Loss (SIM): {pos.token_symbol} | {closed_pos.pnl_percent:+.1f}%")
                            await self.alerts.stop_loss(pos.token_symbol, closed_pos.pnl_percent, pnl_sol_override)
                            await self._learn_from_closed_trade(
                                pos,
                                "SL",
                                exit_price_override=exit_price,
                                sol_returned_override=sol_returned,
                                pnl_percent_override=pnl_percent_override
                            )
                            
                            # ADD COOLDOWN: Don't re-enter this token for 5 minutes
                            import time
                            self.token_cooldown[pos.token_mint] = time.time() + (self.COOLDOWN_MINUTES * 60)
                            logger.info(f"   ⏳ {pos.token_symbol} in cooldown for {self.COOLDOWN_MINUTES} minutes")
                        else:
                            logger.info(f"🎯 Take Profit (SIM): {pos.token_symbol} | {closed_pos.pnl_percent:+.1f}%")
                            await self.alerts.take_profit(pos.token_symbol, closed_pos.pnl_percent, pnl_sol_override)
                            await self._learn_from_closed_trade(
                                pos,
                                "TP",
                                exit_price_override=exit_price,
                                sol_returned_override=sol_returned,
                                pnl_percent_override=pnl_percent_override
                            )
                        
                        self.positions.close_position(pos.id)
                        break
            
            # ═══════════════════════════════════════════════════════════════════
            # Show CURRENT position status (even if no trades closed)
            # ═══════════════════════════════════════════════════════════════════
            if self.simulator.positions:
                logger.info("═" * 60)
                logger.info("📈 OPEN POSITIONS STATUS:")
                logger.info("═" * 60)
                
                total_pnl = 0
                for token, pos in self.simulator.positions.items():
                    if pos.current_price and pos.entry_price > 0:
                        pnl_pct = ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
                        total_pnl += pnl_pct
                        
                        # Emoji based on P&L
                        emoji = "🟢" if pnl_pct >= 0 else "🔴"
                        
                        # stop_loss/take_profit are percentages (15.0 = 15%)
                        logger.info(
                            f"  {emoji} {pos.token_symbol}: "
                            f"Entry ${pos.entry_price:.8f} → Now ${pos.current_price:.8f} | "
                            f"P&L: {pnl_pct:+.1f}% | "
                            f"SL: -{pos.stop_loss:.0f}% TP: +{pos.take_profit:.0f}%"
                        )
                
                avg_pnl = total_pnl / len(self.simulator.positions) if self.simulator.positions else 0
                logger.info("═" * 60)
                logger.info(f"📊 Portfolio: {len(self.simulator.positions)} positions | Avg P&L: {avg_pnl:+.1f}%")
                logger.info("═" * 60)
            
            # Print simulator stats if any trades closed
            if self.simulator.stats.total_trades > 0:
                logger.info(self.simulator.get_summary())
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # REAL MODE: Execute actual sells
        # ═══════════════════════════════════════════════════════════════════
        # Update prices
        self.positions.update_all_prices(prices)
        
        # Check triggers
        sl_positions, tp_positions = self.positions.check_triggers()
        
        # Handle stop losses
        for pos in sl_positions:
            logger.warning(f"🛑 Stop Loss: {pos.token_symbol}")
            
            result = await self.swap.sell_token(
                pos.token_mint,
                pos.amount
            )
            
            if result.success:
                await self.alerts.stop_loss(pos.token_symbol, pos.pnl_percent, pos.pnl_sol)
                
                # REACTIVE LEARNING: Learn from this loss
                await self._learn_from_closed_trade(pos, "SL")
                
                self.positions.close_position(pos.id)
        
        # Handle take profits
        for pos in tp_positions:
            logger.info(f"🎯 Take Profit: {pos.token_symbol}")
            
            result = await self.swap.sell_token(
                pos.token_mint,
                pos.amount
            )
            
            if result.success:
                await self.alerts.take_profit(pos.token_symbol, pos.pnl_percent, pos.pnl_sol)
                
                # REACTIVE LEARNING: Learn from this win
                await self._learn_from_closed_trade(pos, "TP")
                
                self.positions.close_position(pos.id)
    
    async def run_cycle(self):
        """Run one scan/analysis cycle - FOCUS MODE: Monitor first, then trade"""
        
        try:
            # ═══════════════════════════════════════════════════════════════════
            # STEP 0: CHECK API HEALTH (every cycle)
            # ═══════════════════════════════════════════════════════════════════
            unhealthy = health_monitor.get_unhealthy()
            if unhealthy:
                logger.warning(f"⚠️ Unhealthy APIs: {unhealthy}")
            
            # ═══════════════════════════════════════════════════════════════════
            # STEP 1: ALWAYS CHECK POSITIONS FIRST (every cycle!)
            # ═══════════════════════════════════════════════════════════════════
            num_positions = len(self.simulator.positions) if self.simulator else len(self.positions.get_all_positions())
            
            if num_positions > 0:
                logger.info(f"💰 Monitoring {num_positions} position(s)...")
                await self.check_positions()
                
                # If we have max positions, just monitor - don't scan
                if num_positions >= config.MAX_POSITIONS:
                    logger.info(f"📊 Max positions reached ({num_positions}/{config.MAX_POSITIONS}) - monitoring only")
                    return
            
            # ═══════════════════════════════════════════════════════════════════
            # STEP 2: SCAN FOR NEW TOKENS (only if we have room)
            # ═══════════════════════════════════════════════════════════════════
            logger.info(f"🔍 Scanning for tokens (slots: {num_positions}/{config.MAX_POSITIONS})...")
            tokens = await self.scan_tokens()
            
            # ═══════════════════════════════════════════════════════════════════
            # STEP 3: OPEN ONE NEW POSITION (focus mode - one at a time)
            # ═══════════════════════════════════════════════════════════════════
            candidates = tokens[:5]
            if not candidates:
                return

            semaphore = asyncio.Semaphore(self.SCAN_CONCURRENCY)
            tasks = []

            async def guarded_process(token_candidate: dict):
                async with semaphore:
                    try:
                        success = await self.process_token(token_candidate)
                        return token_candidate, success, None
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.error(
                            f"Token worker error for {token_candidate.get('mint', '')[:8]}...: {exc}"
                        )
                        return token_candidate, False, exc

            for token in candidates:
                if self.simulator and token.get("mint") in self.simulator.positions:
                    continue
                tasks.append(asyncio.create_task(guarded_process(token)))

            if not tasks:
                return

            opened_token = None

            try:
                for task in asyncio.as_completed(tasks):
                    try:
                        token_info, success, error = await task
                    except asyncio.CancelledError:
                        continue

                    if error is not None:
                        continue

                    if success:
                        opened_token = token_info
                        for other in tasks:
                            if other is not task and not other.done():
                                other.cancel()
                        break
            finally:
                await asyncio.gather(*tasks, return_exceptions=True)

            if opened_token:
                logger.info("✅ Position opened! Now monitoring...")
                await asyncio.sleep(2)
                await self.check_positions()
            
        except Exception as e:
            logger.error(f"Cycle error: {e}")
            self.api_errors += 1
            await self.alerts.error(str(e))
    
    async def start(self):
        """Start the bot"""
        
        logger.info("=" * 60)
        logger.info("           🚀 NEXUS AI - SOLANA EDITION 🚀")
        logger.info("       🛡️  With Resilient Infrastructure 🛡️")
        if self.simulation_mode:
            logger.info("         📊 SIMULATION MODE - PAPER TRADING 📊")
            logger.info(f"         Starting balance: {config.SIMULATION_STARTING_SOL} SOL")
        logger.info("=" * 60)
        
        # Validate config
        errors = Config.validate()
        for e in errors:
            logger.warning(e)
        
        if not config.DEEPSEEK_API_KEY:
            logger.error("DEEPSEEK_API_KEY is required!")
            return
        
        # Print config
        Config.print_config()
        
        # ═══════════════════════════════════════════════════════════════════
        # START HEALTH MONITORING
        # ═══════════════════════════════════════════════════════════════════
        await health_monitor.start_monitoring(check_interval=30.0)
        logger.info("💓 Health monitoring started")

        # ═══════════════════════════════════════════════════════════════════
        # START DASHBOARD API
        # ═══════════════════════════════════════════════════════════════════
        from api_server import start_api_server
        self._api_runner = await start_api_server()
        logger.info("📊 Dashboard API started on :8080")
        
        # Send startup alert
        await self.alerts.startup()
        
        self.running = True
        await self._update_scan_cache(force=True)
        if not self._scan_refresher_task:
            self._scan_refresher_task = asyncio.create_task(self._scan_refresh_loop())

        logger.info(f"Starting main loop (interval: {config.SCAN_INTERVAL}s)")
        logger.info("Press Ctrl+C to stop\n")
        
        while self.running:
            try:
                await self.run_cycle()
                await asyncio.sleep(config.SCAN_INTERVAL)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(30)
        
        await self.stop()
    
    async def _record_trade(self, token_data: dict, decision, sol_amount: float, token_amount: float, is_simulated: bool = False):
        """Record a trade in the database without blocking the loop."""
        try:
            trade = TradeRecord(
                id=None,
                token_mint=token_data["mint"],
                token_symbol=token_data.get("symbol", "???"),
                side="BUY",
                entry_price=token_data["price"],
                is_simulated=is_simulated,
                exit_price=None,
                amount=token_amount,
                sol_invested=sol_amount,
                sol_returned=None,
                pnl_sol=None,
                pnl_percent=None,
                token_score=decision.token_score,
                sentiment_score=decision.sentiment_score,
                risk_score=decision.risk_score,
                ai_confidence=decision.confidence,
                liquidity=token_data.get("liquidity", 0),
                volume_24h=token_data.get("volume_24h", 0),
                holder_count=token_data.get("holder_count", 0),
                age_hours=token_data.get("age_hours", 0),
                top_10_percent=token_data.get("top_10_percent", 0),
                outcome="OPEN",
                hold_time_hours=None,
                exit_reason=None,
                entry_time=datetime.now().isoformat(),
                exit_time=None,
                extra_data=f'{{"is_simulated": {str(is_simulated).lower()}}}'
            )
            await asyncio.to_thread(self.db.add_trade, trade)
            mint = token_data.get("mint")
            if mint:
                self.known_mints.add(mint)
            
            if is_simulated:
                logger.debug(f"Trade recorded (SIMULATED): {token_data.get('symbol')}")
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
    
    async def _record_scan(self, token_data: dict, ai_decision: str, confidence: int, decision=None):
        """Record a token scan for learning (even skipped ones)"""
        try:
            scan = TokenScan(
                id=None,
                token_mint=token_data["mint"],
                token_symbol=token_data.get("symbol", "???"),
                scan_time=datetime.now().isoformat(),
                price=token_data.get("price", 0),
                liquidity=token_data.get("liquidity", 0),
                volume_24h=token_data.get("volume_24h", 0),
                holder_count=token_data.get("holder_count", 0),
                age_hours=token_data.get("age_hours", 0),
                ai_decision=ai_decision,
                ai_confidence=confidence,
                token_score=decision.token_score if decision else 0,
                sentiment_score=decision.sentiment_score if decision else 0,
                risk_score=decision.risk_score if decision else 0
            )
            await asyncio.to_thread(self.db.add_scan, scan)
            mint = token_data.get("mint")
            if mint:
                self.known_mints.add(mint)
        except Exception as e:
            logger.debug(f"Failed to record scan: {e}")
    
    async def _learn_from_closed_trade(
        self,
        position,
        exit_reason: str,
        *,
        exit_price_override: Optional[float] = None,
        sol_returned_override: Optional[float] = None,
        pnl_percent_override: Optional[float] = None
    ):
        """
        REACTIVE LEARNING: Learn immediately when a trade closes
        
        This is what makes the AI truly reactive - it adjusts weights
        after EVERY single trade, not waiting for batch analysis.
        """
        try:
            trade = await asyncio.to_thread(
                self.db.get_latest_open_trade_by_mint, position.token_mint
            )

            if not trade:
                logger.warning("Could not find trade for reactive learning")
                return

            entry_time = datetime.fromisoformat(trade.entry_time)
            hold_hours = (datetime.now() - entry_time).total_seconds() / 3600

            # Determine overrides
            exit_price = exit_price_override if exit_price_override is not None else position.current_price
            pnl_percent = pnl_percent_override if pnl_percent_override is not None else position.pnl_percent
            if sol_returned_override is not None:
                sol_returned = sol_returned_override
            else:
                sol_returned = position.sol_invested + (position.sol_invested * (pnl_percent / 100))
            pnl_sol = sol_returned - position.sol_invested
            
            # Create outcome for reactive learning
            outcome = TradeOutcome(
                token_mint=position.token_mint,
                pnl_percent=pnl_percent,
                hold_time_hours=hold_hours,
                entry_liquidity=trade.liquidity or 0,
                entry_holders=trade.holder_count or 0,
                entry_age_hours=trade.age_hours or 0,
                entry_volume=trade.volume_24h or 0,
                token_score=trade.token_score or 0,
                sentiment_score=trade.sentiment_score or 0,
                risk_score=trade.risk_score or 0,
                confidence=trade.ai_confidence or 0,
                had_whale_signal=False,  # TODO: Track this in trades table
                whale_was_buying=False
            )
            
            # LEARN!
            self.reactive.learn_from_trade(outcome)
            
            # Also close in DB
            await asyncio.to_thread(
                self.db.close_trade,
                trade_id=trade.id,
                exit_price=exit_price,
                sol_returned=sol_returned,
                exit_reason=exit_reason
            )
            
        except Exception as e:
            logger.error(f"Reactive learning error: {e}")
    
    async def stop(self):
        """Stop the bot gracefully"""
        
        logger.info("\nStopping NEXUS...")
        self.running = False

        if self._scan_refresher_task:
            self._scan_refresher_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._scan_refresher_task
            self._scan_refresher_task = None
        
        # Stop health monitoring
        await health_monitor.stop_monitoring()
        
        # Run learning analysis before shutdown
        logger.info("🧠 Running learning analysis...")
        await asyncio.to_thread(self.learning.analyze_and_learn)
        
        # Close connections
        await self.birdeye.close()
        await self.dexscreener.close()
        await self.whale_tracker.close()
        await self.scan_updater.close()
        await self.rug_checker.close()
        await self.swap.close()
        await asyncio.to_thread(self.db.close)
        
        # Send shutdown alert
        await self.alerts.shutdown()
        
        # Print summary
        stats = await asyncio.to_thread(self.db.get_stats, days=1) if hasattr(self, 'db') else {}
        logger.info("\n" + "=" * 60)
        logger.info("                    SESSION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"  Tokens Analyzed: {self.tokens_analyzed}")
        logger.info(f"  Trades Executed: {self.trades_executed}")
        logger.info(f"  Open Positions: {self.positions.get_position_count()}")
        logger.info(f"  Total PnL: {self.positions.get_total_pnl():+.4f} SOL")
        if stats:
            logger.info(f"  Win Rate (24h): {stats.get('win_rate', 0):.1f}%")
        
        # Infrastructure stats
        logger.info("")
        logger.info("  📊 INFRASTRUCTURE STATS:")
        logger.info(f"  API Errors: {self.api_errors}")
        logger.info(f"  Rate Limited: {self.rate_limited_calls}")
        
        api_health = self.get_api_health_status()
        logger.info(f"  APIs Healthy: {len([a for a in api_health['apis'].values() if a['healthy']])}/{len(api_health['apis'])}")
        
        # Show rate limiter stats
        rl_stats = rate_limiter.get_stats()
        total_requests = sum(s.total_requests for s in rl_stats.values())
        total_retries = sum(s.retries for s in rl_stats.values())
        logger.info(f"  Total API Calls: {total_requests}")
        logger.info(f"  Total Retries: {total_retries}")
        
        logger.info("=" * 60)
        
        logger.info("NEXUS stopped. Goodbye! 👋")


# ═══════════════════════════════════════════════════════════════════════════════
#                              ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info("\nShutdown signal received...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run bot
    bot = NexusBot()
    asyncio.run(bot.start())


if __name__ == "__main__":
    main()
