"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    NEXUS AI - Circuit Breaker & Fallback                      ║
║         Resilient API handling with health monitoring                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, Any, List, TypeVar, Generic
from enum import Enum
from loguru import logger
import functools
from datetime import datetime, timedelta

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"           # Normal operation
    OPEN = "open"               # Failing, reject requests
    HALF_OPEN = "half_open"     # Testing recovery


@dataclass
class CircuitConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 3          # Successes to close from half-open
    timeout: float = 30.0               # Seconds before trying again
    half_open_max_calls: int = 3        # Max calls in half-open state
    failure_rate_threshold: float = 0.5 # Failure rate to open
    min_calls: int = 10                 # Min calls before checking rate


@dataclass 
class CircuitStats:
    """Circuit breaker statistics"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure: Optional[float] = None
    last_success: Optional[float] = None
    last_state_change: Optional[float] = None


@dataclass
class HealthStatus:
    """API health status"""
    api_name: str
    is_healthy: bool
    latency_avg_ms: float
    success_rate: float
    last_check: datetime
    consecutive_failures: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED


class CircuitBreaker:
    """
    Circuit Breaker Pattern
    
    Prevents cascading failures by:
    - Tracking failure rates
    - Opening circuit after threshold
    - Testing recovery with half-open state
    """
    
    def __init__(self, name: str, config: CircuitConfig = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        
        # Sliding window for recent calls
        self._recent_calls: List[tuple] = []  # (timestamp, success)
        self._window_size = 60.0  # 60 second window
        
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        
        self._lock = asyncio.Lock()
    
    async def can_execute(self) -> bool:
        """Check if request can proceed"""
        async with self._lock:
            now = time.monotonic()
            
            if self.state == CircuitState.CLOSED:
                return True
                
            elif self.state == CircuitState.OPEN:
                # Check if timeout elapsed
                if now - self._last_failure_time >= self.config.timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                self.stats.rejected_calls += 1
                return False
                
            elif self.state == CircuitState.HALF_OPEN:
                # Allow limited calls
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
        
        return False
    
    async def record_success(self):
        """Record successful call"""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.successful_calls += 1
            self.stats.last_success = time.monotonic()
            
            self._record_call(True)
            
            if self.state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            
            elif self.state == CircuitState.CLOSED:
                self._failure_count = 0
    
    async def record_failure(self, error: Exception = None):
        """Record failed call"""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.failed_calls += 1
            self.stats.last_failure = time.monotonic()
            self._last_failure_time = time.monotonic()
            
            self._record_call(False)
            
            if self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
                
            elif self.state == CircuitState.CLOSED:
                self._failure_count += 1
                
                # Check failure threshold
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    
                # Check failure rate
                elif self._should_check_rate():
                    rate = self._calculate_failure_rate()
                    if rate >= self.config.failure_rate_threshold:
                        self._transition_to(CircuitState.OPEN)
    
    def _record_call(self, success: bool):
        """Record call in sliding window"""
        now = time.monotonic()
        self._recent_calls.append((now, success))
        
        # Clean old entries
        cutoff = now - self._window_size
        self._recent_calls = [
            (t, s) for t, s in self._recent_calls if t > cutoff
        ]
    
    def _should_check_rate(self) -> bool:
        """Check if we have enough calls to calculate rate"""
        return len(self._recent_calls) >= self.config.min_calls
    
    def _calculate_failure_rate(self) -> float:
        """Calculate failure rate in sliding window"""
        if not self._recent_calls:
            return 0.0
        failures = sum(1 for _, success in self._recent_calls if not success)
        return failures / len(self._recent_calls)
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to new state"""
        old_state = self.state
        self.state = new_state
        self.stats.state_changes += 1
        self.stats.last_state_change = time.monotonic()
        
        # Reset counters
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0
        
        logger.warning(
            f"Circuit {self.name}: {old_state.value} -> {new_state.value}"
        )
    
    def get_state(self) -> CircuitState:
        """Get current state"""
        return self.state
    
    def get_stats(self) -> CircuitStats:
        """Get statistics"""
        return self.stats
    
    def reset(self):
        """Reset circuit breaker"""
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._recent_calls.clear()
        logger.info(f"Circuit {self.name} reset")


class FallbackChain(Generic[T]):
    """
    Fallback Chain for API redundancy
    
    Tries multiple data sources in order until one succeeds
    """
    
    def __init__(self, name: str):
        self.name = name
        self._sources: List[tuple] = []  # (name, func, priority)
        self._stats: Dict[str, int] = {}  # source -> success count
        self._last_successful: Optional[str] = None
    
    def add_source(
        self,
        name: str,
        func: Callable[..., T],
        priority: int = 0
    ):
        """Add a fallback source"""
        self._sources.append((name, func, priority))
        self._sources.sort(key=lambda x: x[2], reverse=True)
        self._stats[name] = 0
        logger.debug(f"Added fallback source: {name} (priority {priority})")
    
    async def execute(self, *args, **kwargs) -> Optional[T]:
        """
        Execute with fallback chain
        
        Returns result from first successful source
        """
        errors = []
        
        # Try last successful first if available
        if self._last_successful:
            sources = list(self._sources)
            # Move last successful to front
            sources.sort(key=lambda x: x[0] == self._last_successful, reverse=True)
        else:
            sources = self._sources
        
        for source_name, func, _ in sources:
            try:
                result = await func(*args, **kwargs)
                if result is not None:
                    self._stats[source_name] += 1
                    self._last_successful = source_name
                    return result
            except Exception as e:
                errors.append((source_name, e))
                logger.debug(f"Fallback {source_name} failed: {e}")
        
        # All failed
        logger.error(
            f"All fallback sources failed for {self.name}: "
            f"{[(n, str(e)) for n, e in errors]}"
        )
        return None
    
    def get_stats(self) -> Dict[str, int]:
        """Get success counts per source"""
        return dict(self._stats)


class HealthMonitor:
    """
    Health Monitor for all API endpoints
    
    Tracks latency, availability, and overall health
    """
    
    def __init__(self):
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._health: Dict[str, HealthStatus] = {}
        self._latencies: Dict[str, List[float]] = {}
        self._check_interval = 30.0
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def register(self, api_name: str, config: CircuitConfig = None):
        """Register an API endpoint"""
        self._circuits[api_name] = CircuitBreaker(api_name, config)
        self._health[api_name] = HealthStatus(
            api_name=api_name,
            is_healthy=True,
            latency_avg_ms=0,
            success_rate=1.0,
            last_check=datetime.now()
        )
        self._latencies[api_name] = []
        logger.info(f"Registered health monitor for {api_name}")
    
    def get_circuit(self, api_name: str) -> CircuitBreaker:
        """Get circuit breaker for API"""
        if api_name not in self._circuits:
            self.register(api_name)
        return self._circuits[api_name]
    
    async def record_call(
        self,
        api_name: str,
        success: bool,
        latency_ms: float,
        error: Exception = None
    ):
        """Record API call result"""
        circuit = self.get_circuit(api_name)
        
        if success:
            await circuit.record_success()
        else:
            await circuit.record_failure(error)
        
        # Track latency
        if api_name not in self._latencies:
            self._latencies[api_name] = []
        self._latencies[api_name].append(latency_ms)
        
        # Keep last 100 measurements
        if len(self._latencies[api_name]) > 100:
            self._latencies[api_name] = self._latencies[api_name][-100:]
        
        # Update health
        await self._update_health(api_name)
    
    async def _update_health(self, api_name: str):
        """Update health status for API"""
        circuit = self._circuits.get(api_name)
        if not circuit:
            return
        
        stats = circuit.get_stats()
        latencies = self._latencies.get(api_name, [])
        
        # Calculate metrics
        if stats.total_calls > 0:
            success_rate = stats.successful_calls / stats.total_calls
        else:
            success_rate = 1.0
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
        else:
            avg_latency = 0
        
        # Determine health
        is_healthy = (
            circuit.state == CircuitState.CLOSED and
            success_rate >= 0.9 and
            avg_latency < 5000  # 5s threshold
        )
        
        self._health[api_name] = HealthStatus(
            api_name=api_name,
            is_healthy=is_healthy,
            latency_avg_ms=avg_latency,
            success_rate=success_rate,
            last_check=datetime.now(),
            consecutive_failures=circuit._failure_count,
            circuit_state=circuit.state
        )
    
    def get_health(self, api_name: str = None) -> Dict[str, HealthStatus]:
        """Get health status"""
        if api_name:
            return {api_name: self._health.get(api_name)}
        return dict(self._health)
    
    def get_all_healthy(self) -> bool:
        """Check if all APIs are healthy"""
        return all(h.is_healthy for h in self._health.values())
    
    def get_unhealthy(self) -> List[str]:
        """Get list of unhealthy APIs"""
        return [name for name, h in self._health.items() if not h.is_healthy]
    
    async def start_monitoring(self, check_interval: float = 30.0):
        """Start background health monitoring"""
        self._check_interval = check_interval
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitoring stopped")
    
    async def _monitor_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                for api_name in self._circuits:
                    await self._update_health(api_name)
                
                # Log unhealthy APIs
                unhealthy = self.get_unhealthy()
                if unhealthy:
                    logger.warning(f"Unhealthy APIs: {unhealthy}")
                
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(self._check_interval)


# Global instances
health_monitor = HealthMonitor()


def with_circuit_breaker(api_name: str):
    """
    Decorator for circuit breaker protection
    
    Usage:
        @with_circuit_breaker("jupiter")
        async def get_price(mint: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            circuit = health_monitor.get_circuit(api_name)
            
            if not await circuit.can_execute():
                raise Exception(f"Circuit open for {api_name}")
            
            start = time.monotonic()
            try:
                result = await func(*args, **kwargs)
                latency = (time.monotonic() - start) * 1000
                await health_monitor.record_call(api_name, True, latency)
                return result
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                await health_monitor.record_call(api_name, False, latency, e)
                raise
        
        return wrapper
    return decorator


async def with_fallback(
    primary: Callable[[], T],
    fallback: Callable[[], T],
    api_name: str = "unknown"
) -> T:
    """Execute with single fallback"""
    try:
        return await primary()
    except Exception as e:
        logger.warning(f"{api_name} primary failed: {e}, trying fallback")
        return await fallback()
