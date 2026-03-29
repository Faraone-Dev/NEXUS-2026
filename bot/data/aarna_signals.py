"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    NEXUS AI - Aarna MCP Signal Provider                       ║
║          Technical Analysis + Composite Signals via Smithery Connect         ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Connects to Aarna MCP server via Smithery Connect API for:
- get_signal_summary   → composite signal (bullish/bearish + breakdown)
- get_latest_features  → full indicator snapshot (RSI, MACD, BB, etc.)
+ 15 more tools (sentiment, ML export, category features, etc.)

Transport: Smithery Connect JSON-RPC over HTTP
Docs: https://smithery.ai/servers/atars-MCP/aarnaai
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Any
from loguru import logger

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from config import config


@dataclass
class SignalSummary:
    """Composite signal from Aarna MCP"""
    symbol: str
    signal: str           # "BULLISH" / "BEARISH" / "NEUTRAL"
    price: float          # Current price
    bullish_count: int    # Number of bullish signals
    bearish_count: int    # Number of bearish signals
    breakdown: dict       # Per-indicator breakdown (rsi_14, macd, ema_cross, etc.)
    timestamp: float
    
    @property
    def is_bullish(self) -> bool:
        return self.signal.upper() == "BULLISH"
    
    @property
    def is_bearish(self) -> bool:
        return self.signal.upper() == "BEARISH"
    
    @property
    def confidence(self) -> float:
        """Derive confidence from signal ratio."""
        total = self.bullish_count + self.bearish_count
        if total == 0:
            return 0.5
        if self.is_bullish:
            return self.bullish_count / total
        return self.bearish_count / total
    
    def to_prompt_str(self) -> str:
        """Format for AI agent prompt injection"""
        parts = [
            f"Signal: {self.signal.upper()} ({self.bullish_count} bullish / {self.bearish_count} bearish)",
            f"Price: ${self.price:,.2f}" if self.price else None,
        ]
        if self.breakdown:
            bd = self.breakdown
            for key, val in bd.items():
                parts.append(f"{key}: {val}")
        return " | ".join(p for p in parts if p)


@dataclass
class IndicatorSnapshot:
    """Full indicator snapshot from Aarna MCP"""
    symbol: str
    indicators: dict      # All raw indicators
    timestamp: float
    
    def get(self, key: str, default=None):
        return self.indicators.get(key, default)
    
    def to_prompt_str(self) -> str:
        """Format key indicators for AI agent prompt"""
        ind = self.indicators
        parts = []
        
        # Core trend indicators
        for key in ["rsi", "rsi_14"]:
            if key in ind:
                parts.append(f"RSI: {ind[key]:.1f}")
                break
        
        if "macd" in ind:
            macd = ind["macd"]
            if isinstance(macd, dict):
                parts.append(f"MACD: {macd.get('value', 'N/A')}, Signal: {macd.get('signal', 'N/A')}")
            else:
                parts.append(f"MACD: {macd}")
        
        if "bollinger_bands" in ind:
            bb = ind["bollinger_bands"]
            if isinstance(bb, dict):
                parts.append(f"BB: Upper={bb.get('upper', 'N/A')}, Lower={bb.get('lower', 'N/A')}")
        
        for key in ["ema_20", "ema_50", "sma_20", "sma_50"]:
            if key in ind:
                parts.append(f"{key.upper()}: {ind[key]:.4f}")
        
        if "atr" in ind:
            parts.append(f"ATR: {ind['atr']:.4f}")
        
        if "volume_sma" in ind:
            parts.append(f"Vol SMA: {ind['volume_sma']:,.0f}")
        
        return " | ".join(parts) if parts else "No indicators available"


class AarnaSignalClient:
    """
    Client for Aarna MCP Server (Technical Analysis signals)
    
    Uses Smithery Connect API (JSON-RPC over HTTP) for reliable access.
    Falls back gracefully if API key not set or server unreachable.
    """
    
    CACHE_TTL = 30  # seconds
    BASE_URL = "https://api.smithery.ai/connect"
    
    def __init__(self):
        self.api_key = config.AARNA_API_KEY
        self.namespace = config.AARNA_NAMESPACE
        self.connection = config.AARNA_CONNECTION
        self.enabled = bool(self.api_key) and HTTPX_AVAILABLE and config.AARNA_ENABLED
        self._cache: dict[str, dict] = {}
        self._session_id: Optional[str] = None
        self._initialized = False
        self._request_id = 0
        
        if not HTTPX_AVAILABLE:
            logger.warning("📊 Aarna MCP: 'httpx' package not installed - TA signals disabled")
        elif not self.api_key:
            logger.warning("📊 Aarna MCP: AARNA_API_KEY not set - TA signals disabled")
        else:
            logger.info(f"📊 Aarna MCP Signal Provider initialized (Smithery Connect)")
    
    @property
    def _mcp_url(self) -> str:
        return f"{self.BASE_URL}/{self.namespace}/{self.connection}/mcp"
    
    @property
    def _headers(self) -> dict:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h
    
    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id
    
    def _cache_key(self, method: str, symbol: str) -> str:
        return f"{method}:{symbol}"
    
    def _get_cached(self, method: str, symbol: str) -> Optional[Any]:
        key = self._cache_key(method, symbol)
        entry = self._cache.get(key)
        if entry and time.time() - entry["timestamp"] < self.CACHE_TTL:
            return entry["data"]
        return None
    
    def _set_cached(self, method: str, symbol: str, data: Any):
        key = self._cache_key(method, symbol)
        self._cache[key] = {"data": data, "timestamp": time.time()}
    
    def _parse_sse_response(self, text: str) -> Optional[dict]:
        """Parse SSE event stream response to extract JSON-RPC result."""
        for line in text.split("\n"):
            if line.startswith("data: "):
                try:
                    return json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
        # Try parsing as plain JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    
    async def _ensure_initialized(self):
        """Initialize MCP session if not already done."""
        if self._initialized:
            return
        
        payload = {
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "nexus-bot", "version": "1.0"}
            }
        }
        
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(self._mcp_url, headers=self._headers, json=payload)
            if r.status_code != 200:
                logger.warning(f"📊 Aarna MCP init failed: {r.status_code}")
                return
            
            self._session_id = r.headers.get("mcp-session-id", "")
            
            # Send initialized notification
            await client.post(
                self._mcp_url, headers=self._headers,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"}
            )
        
        self._initialized = True
        logger.debug("📊 Aarna MCP session initialized")
    
    async def _call_tool(self, tool_name: str, arguments: dict) -> Optional[dict]:
        """Call an MCP tool via Smithery Connect JSON-RPC."""
        if not self.enabled:
            return None
        
        try:
            await self._ensure_initialized()
            
            payload = {
                "jsonrpc": "2.0", "id": self._next_id(), "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments}
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(self._mcp_url, headers=self._headers, json=payload)
                
                if r.status_code != 200:
                    logger.warning(f"📊 Aarna MCP {tool_name}: HTTP {r.status_code}")
                    return None
                
                data = self._parse_sse_response(r.text)
                if not data:
                    return None
                
                content = data.get("result", {}).get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        return json.loads(block["text"])
                
                return None
        except asyncio.TimeoutError:
            logger.warning(f"📊 Aarna MCP timeout: {tool_name}")
            return None
        except Exception as e:
            logger.debug(f"📊 Aarna MCP error ({tool_name}): {e}")
            return None
    
    async def get_signal_summary(self, symbol: str) -> Optional[SignalSummary]:
        """
        Get composite signal summary for a symbol.
        
        Returns bullish/bearish/neutral + trend regime, momentum, volatility context.
        Best for: Master Decision agent.
        """
        cached = self._get_cached("signal_summary", symbol)
        if cached:
            return cached
        
        raw = await self._call_tool("get_signal_summary", {"symbol": symbol})
        if not raw:
            return None
        
        # Actual response format:
        # {symbol, datetime, price, overall, bullish_signals, bearish_signals, details: {rsi_14, macd, ...}}
        summary = SignalSummary(
            symbol=symbol,
            signal=raw.get("overall", "NEUTRAL"),
            price=float(raw.get("price", 0)),
            bullish_count=int(raw.get("bullish_signals", 0)),
            bearish_count=int(raw.get("bearish_signals", 0)),
            breakdown=raw.get("details", {}),
            timestamp=time.time()
        )
        
        self._set_cached("signal_summary", symbol, summary)
        logger.info(f"📊 Aarna signal for {symbol}: {summary.signal.upper()} ({summary.confidence:.0%})")
        return summary
    
    async def get_latest_features(self, symbol: str) -> Optional[IndicatorSnapshot]:
        """
        Get full indicator snapshot (RSI, MACD, BB, EMA, ATR, etc.)
        
        Best for: Token Analyzer agent, detailed technical context.
        """
        cached = self._get_cached("latest_features", symbol)
        if cached:
            return cached
        
        raw = await self._call_tool("get_latest_features", {"symbol": symbol})
        if not raw:
            return None
        
        snapshot = IndicatorSnapshot(
            symbol=symbol,
            indicators=raw.get("features", raw) if isinstance(raw, dict) else {},
            timestamp=time.time()
        )
        
        self._set_cached("latest_features", symbol, snapshot)
        logger.info(f"📊 Aarna features for {symbol}: {len(snapshot.indicators)} indicators")
        return snapshot
    
    async def get_signals_for_token(self, symbol: str) -> dict:
        """
        Convenience method: fetch both signal summary + features in parallel.
        Returns a dict ready to merge into the token's all_data dict.
        
        Used by NexusBot.analyze_token() to enrich data before AI analysis.
        """
        if not self.enabled:
            return {}
        
        # Map Solana memecoin symbols to tradeable pairs if needed
        # Aarna supports standard symbols (BTC, ETH, SOL, etc.)
        mapped_symbol = self._map_symbol(symbol)
        if not mapped_symbol:
            return {}
        
        try:
            summary_task = self.get_signal_summary(mapped_symbol)
            features_task = self.get_latest_features(mapped_symbol)
            
            summary, features = await asyncio.gather(
                summary_task, features_task, return_exceptions=True
            )
            
            if isinstance(summary, Exception):
                summary = None
            if isinstance(features, Exception):
                features = None
            
        except Exception as e:
            logger.debug(f"📊 Aarna signal fetch failed for {symbol}: {e}")
            return {}
        
        result = {}
        
        if summary and isinstance(summary, SignalSummary):
            result["ta_signal"] = summary.signal
            result["ta_confidence"] = summary.confidence
            result["ta_price"] = summary.price
            result["ta_bullish_count"] = summary.bullish_count
            result["ta_bearish_count"] = summary.bearish_count
            result["ta_signal_summary"] = summary.to_prompt_str()
            result["ta_breakdown"] = summary.breakdown
        
        if features and isinstance(features, IndicatorSnapshot):
            result["ta_indicators"] = features.indicators
            result["ta_indicators_summary"] = features.to_prompt_str()
            # Extract key values for direct use
            ind = features.indicators
            for key in ["rsi", "rsi_14"]:
                if key in ind:
                    result["ta_rsi"] = ind[key]
                    break
            if "macd" in ind:
                result["ta_macd"] = ind["macd"]
            if "atr" in ind:
                result["ta_atr"] = ind["atr"]
        
        return result
    
    def _map_symbol(self, symbol: str) -> Optional[str]:
        """
        Map Solana token symbols to Aarna-compatible symbols.
        
        Aarna uses standard symbols (BTC, ETH, SOL, etc.)
        For memecoins without standard TA data, we return None
        (TA is most useful for tokens that have enough history).
        """
        if not symbol:
            return None
        
        sym = symbol.upper().strip()
        
        # Direct pass-through for tokens Aarna actually supports (17 tokens)
        SUPPORTED = {
            "ADA", "AVAX", "BCH", "BNB", "BTC", "DOGE", "ETH",
            "HBAR", "LINK", "LTC", "SHIB", "SOL", "SUI", "TRX",
            "XLM", "XRP", "ZEC",
        }
        
        if sym in SUPPORTED:
            return sym
        
        # For unknown memecoins, still try — Aarna may support more than we know
        # Return the symbol as-is; the server will return empty if unsupported
        return sym
