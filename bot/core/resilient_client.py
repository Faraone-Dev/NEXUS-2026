"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    NEXUS AI - Resilient API Client                            ║
║       Combines Rate Limiting + Circuit Breaker + Fallback + Monitoring        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import time
import httpx
from typing import Dict, Any, Optional, Callable, TypeVar, List
from dataclasses import dataclass
from loguru import logger

from .rate_limiter import rate_limiter, RateLimitConfig
from .circuit_breaker import health_monitor, CircuitConfig, FallbackChain


T = TypeVar('T')


@dataclass
class APIEndpoint:
    """API endpoint configuration"""
    name: str
    base_url: str
    rate_limit: RateLimitConfig
    circuit_config: CircuitConfig
    headers: Dict[str, str] = None
    timeout: float = 30.0


class ResilientClient:
    """
    Resilient HTTP client with:
    - Rate limiting (Token Bucket)
    - Circuit breaker (Fail fast)
    - Automatic retries (Exponential backoff)
    - Health monitoring
    - Request queuing
    """
    
    # Pre-configured API settings
    API_CONFIGS = {
        "jupiter": APIEndpoint(
            name="jupiter",
            base_url="https://api.jup.ag",
            rate_limit=RateLimitConfig(
                requests_per_second=10,
                burst_size=20,
                max_retries=3
            ),
            circuit_config=CircuitConfig(
                failure_threshold=5,
                timeout=30
            )
        ),
        "birdeye": APIEndpoint(
            name="birdeye",
            base_url="https://public-api.birdeye.so",
            rate_limit=RateLimitConfig(
                requests_per_second=5,
                burst_size=10,
                max_retries=3
            ),
            circuit_config=CircuitConfig(
                failure_threshold=3,
                timeout=60
            )
        ),
        "dexscreener": APIEndpoint(
            name="dexscreener",
            base_url="https://api.dexscreener.com",
            rate_limit=RateLimitConfig(
                requests_per_second=5,
                burst_size=15,
                max_retries=3
            ),
            circuit_config=CircuitConfig(
                failure_threshold=5,
                timeout=30
            )
        ),
        "helius": APIEndpoint(
            name="helius",
            base_url="https://api.helius.xyz",
            rate_limit=RateLimitConfig(
                requests_per_second=10,
                burst_size=30,
                max_retries=3
            ),
            circuit_config=CircuitConfig(
                failure_threshold=5,
                timeout=30
            )
        ),
        "rugcheck": APIEndpoint(
            name="rugcheck",
            base_url="https://api.rugcheck.xyz",
            rate_limit=RateLimitConfig(
                requests_per_second=2,
                burst_size=5,
                max_retries=5
            ),
            circuit_config=CircuitConfig(
                failure_threshold=3,
                timeout=120
            )
        ),
    }
    
    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._fallback_chains: Dict[str, FallbackChain] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize clients and monitoring"""
        if self._initialized:
            return
        
        for api_name, config in self.API_CONFIGS.items():
            # Configure rate limiter
            rate_limiter.configure(api_name, config.rate_limit)
            
            # Register with health monitor
            health_monitor.register(api_name, config.circuit_config)
            
            # Create HTTP client
            headers = config.headers or {}
            self._clients[api_name] = httpx.AsyncClient(
                base_url=config.base_url,
                headers=headers,
                timeout=config.timeout
            )
        
        # Start health monitoring
        await health_monitor.start_monitoring()
        
        self._initialized = True
        logger.info("Resilient client initialized")
    
    async def close(self):
        """Close all clients"""
        await health_monitor.stop_monitoring()
        
        for client in self._clients.values():
            await client.aclose()
        
        self._initialized = False
        logger.info("Resilient client closed")
    
    async def request(
        self,
        api_name: str,
        method: str,
        path: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Make resilient API request
        
        Automatically handles:
        - Rate limiting
        - Circuit breaker
        - Retries
        - Error logging
        """
        if not self._initialized:
            await self.initialize()
        
        circuit = health_monitor.get_circuit(api_name)
        
        # Check circuit
        if not await circuit.can_execute():
            logger.warning(f"{api_name} circuit open, skipping request")
            return None
        
        async def make_request():
            client = self._clients.get(api_name)
            if not client:
                raise ValueError(f"Unknown API: {api_name}")
            
            start = time.monotonic()
            response = await client.request(method, path, **kwargs)
            latency = (time.monotonic() - start) * 1000
            
            response.raise_for_status()
            
            # Record success
            await health_monitor.record_call(api_name, True, latency)
            
            return response.json()
        
        try:
            return await rate_limiter.execute_with_retry(api_name, make_request)
        except Exception as e:
            await health_monitor.record_call(api_name, False, 0, e)
            logger.error(f"{api_name} request failed: {e}")
            return None
    
    async def get(self, api_name: str, path: str, **kwargs) -> Optional[Dict[str, Any]]:
        """GET request"""
        return await self.request(api_name, "GET", path, **kwargs)
    
    async def post(self, api_name: str, path: str, **kwargs) -> Optional[Dict[str, Any]]:
        """POST request"""
        return await self.request(api_name, "POST", path, **kwargs)
    
    def register_fallback(
        self,
        name: str,
        primary_func: Callable,
        fallback_funcs: List[Callable]
    ):
        """Register fallback chain for a data source"""
        chain = FallbackChain(name)
        chain.add_source("primary", primary_func, priority=100)
        
        for i, func in enumerate(fallback_funcs):
            chain.add_source(f"fallback_{i}", func, priority=50 - i * 10)
        
        self._fallback_chains[name] = chain
    
    async def with_fallback(self, name: str, *args, **kwargs) -> Optional[Any]:
        """Execute with fallback chain"""
        chain = self._fallback_chains.get(name)
        if not chain:
            raise ValueError(f"No fallback chain registered: {name}")
        
        return await chain.execute(*args, **kwargs)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary of all APIs"""
        health = health_monitor.get_health()
        stats = rate_limiter.get_stats()
        
        summary = {
            'all_healthy': health_monitor.get_all_healthy(),
            'unhealthy_apis': health_monitor.get_unhealthy(),
            'apis': {}
        }
        
        for api_name in self.API_CONFIGS:
            api_health = health.get(api_name)
            api_stats = stats.get(api_name)
            
            if api_health:
                summary['apis'][api_name] = {
                    'healthy': api_health.is_healthy,
                    'circuit_state': api_health.circuit_state.value,
                    'success_rate': f"{api_health.success_rate:.1%}",
                    'avg_latency_ms': f"{api_health.latency_avg_ms:.1f}",
                    'total_requests': api_stats.total_requests if api_stats else 0,
                    'rate_limited': api_stats.rate_limited if api_stats else 0,
                }
        
        return summary


# Global client instance
resilient_client = ResilientClient()


# Convenience decorators
def resilient(api_name: str):
    """Decorator for resilient API calls"""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            circuit = health_monitor.get_circuit(api_name)
            
            if not await circuit.can_execute():
                return None
            
            start = time.monotonic()
            try:
                result = await rate_limiter.execute_with_retry(
                    api_name,
                    lambda: func(*args, **kwargs)
                )
                latency = (time.monotonic() - start) * 1000
                await health_monitor.record_call(api_name, True, latency)
                return result
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                await health_monitor.record_call(api_name, False, latency, e)
                raise
        
        return wrapper
    return decorator
