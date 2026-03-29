"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     NEXUS AI - Advanced Rate Limiter                          ║
║           Token Bucket + Exponential Backoff + Queue Management               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, Any, TypeVar, Generic
from collections import deque
from enum import Enum
from loguru import logger
import functools

T = TypeVar('T')


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    TOKEN_BUCKET = "token_bucket"      # Classic token bucket
    SLIDING_WINDOW = "sliding_window"  # Sliding window log
    FIXED_WINDOW = "fixed_window"      # Fixed time window


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_second: float = 10.0
    burst_size: int = 20                    # Max burst capacity
    max_retries: int = 5                    # Retry attempts
    base_delay: float = 1.0                 # Initial retry delay
    max_delay: float = 60.0                 # Max retry delay
    exponential_base: float = 2.0           # Backoff multiplier
    jitter: bool = True                     # Add random jitter
    queue_size: int = 1000                  # Max queued requests
    timeout: float = 30.0                   # Request timeout


@dataclass
class RateLimitStats:
    """Statistics for rate limiter"""
    total_requests: int = 0
    successful_requests: int = 0
    rate_limited: int = 0
    retries: int = 0
    queue_high_watermark: int = 0
    avg_wait_time: float = 0.0
    last_reset: float = field(default_factory=time.time)


class TokenBucket:
    """
    Token Bucket Rate Limiter
    
    Allows burst traffic while maintaining average rate
    """
    
    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Tokens added per second
            capacity: Maximum bucket capacity
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, waiting if necessary
        
        Returns: Time waited in seconds
        """
        async with self._lock:
            wait_time = 0.0
            
            # Refill tokens
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            # Wait if not enough tokens
            if self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = tokens  # Refilled during wait
            
            self.tokens -= tokens
            return wait_time
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting"""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class SlidingWindowLog:
    """
    Sliding Window Rate Limiter
    
    More accurate but uses more memory
    """
    
    def __init__(self, rate: float, window_seconds: float = 1.0):
        self.rate = rate
        self.window = window_seconds
        self.timestamps: deque = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> float:
        """Acquire a slot, waiting if necessary"""
        async with self._lock:
            now = time.monotonic()
            wait_time = 0.0
            
            # Remove expired timestamps
            cutoff = now - self.window
            while self.timestamps and self.timestamps[0] < cutoff:
                self.timestamps.popleft()
            
            # Check if over limit
            max_requests = int(self.rate * self.window)
            if len(self.timestamps) >= max_requests:
                oldest = self.timestamps[0]
                wait_time = oldest + self.window - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    now = time.monotonic()
                    # Clean again after wait
                    cutoff = now - self.window
                    while self.timestamps and self.timestamps[0] < cutoff:
                        self.timestamps.popleft()
            
            self.timestamps.append(now)
            return wait_time


class ExponentialBackoff:
    """
    Exponential Backoff with Jitter
    
    For handling rate limit errors gracefully
    """
    
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.attempt = 0
    
    def next_delay(self) -> float:
        """Calculate next retry delay"""
        import random
        
        delay = self.base_delay * (self.exponential_base ** self.attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Full jitter: random between 0 and delay
            delay = random.uniform(0, delay)
        
        self.attempt += 1
        return delay
    
    def reset(self):
        """Reset attempt counter"""
        self.attempt = 0


class RequestQueue(Generic[T]):
    """
    Priority request queue with timeout handling
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._pending: Dict[str, asyncio.Future] = {}
        self._stats = RateLimitStats()
    
    async def enqueue(
        self,
        request_id: str,
        priority: int = 0,
        timeout: float = 30.0
    ) -> asyncio.Future:
        """Add request to queue"""
        if self._queue.full():
            raise asyncio.QueueFull("Request queue is full")
        
        future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future
        
        await self._queue.put((priority, time.monotonic(), request_id))
        self._stats.queue_high_watermark = max(
            self._stats.queue_high_watermark,
            self._queue.qsize()
        )
        
        return future
    
    async def dequeue(self) -> Optional[str]:
        """Get next request from queue"""
        try:
            _, _, request_id = await asyncio.wait_for(
                self._queue.get(),
                timeout=1.0
            )
            return request_id
        except asyncio.TimeoutError:
            return None
    
    def complete(self, request_id: str, result: Any):
        """Mark request as complete"""
        if request_id in self._pending:
            future = self._pending.pop(request_id)
            if not future.done():
                future.set_result(result)
    
    def fail(self, request_id: str, error: Exception):
        """Mark request as failed"""
        if request_id in self._pending:
            future = self._pending.pop(request_id)
            if not future.done():
                future.set_exception(error)


class RateLimiter:
    """
    Main Rate Limiter with multiple strategies
    
    Features:
    - Token bucket for burst handling
    - Exponential backoff for retries
    - Request queuing
    - Per-endpoint limits
    - Statistics tracking
    """
    
    # Default limits for known APIs
    DEFAULT_LIMITS = {
        "jupiter": RateLimitConfig(requests_per_second=10, burst_size=20),
        "birdeye": RateLimitConfig(requests_per_second=5, burst_size=10),
        "dexscreener": RateLimitConfig(requests_per_second=5, burst_size=15),
        "helius": RateLimitConfig(requests_per_second=10, burst_size=30),
        "rugcheck": RateLimitConfig(requests_per_second=2, burst_size=5),
        "default": RateLimitConfig(requests_per_second=5, burst_size=10),
    }
    
    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._configs: Dict[str, RateLimitConfig] = {}
        self._stats: Dict[str, RateLimitStats] = {}
        self._backoffs: Dict[str, ExponentialBackoff] = {}
        self._lock = asyncio.Lock()
        
        logger.info("Rate limiter initialized")
    
    def configure(self, api_name: str, config: RateLimitConfig):
        """Configure rate limits for an API"""
        self._configs[api_name] = config
        self._buckets[api_name] = TokenBucket(
            rate=config.requests_per_second,
            capacity=config.burst_size
        )
        self._stats[api_name] = RateLimitStats()
        self._backoffs[api_name] = ExponentialBackoff(
            base_delay=config.base_delay,
            max_delay=config.max_delay,
            exponential_base=config.exponential_base,
            jitter=config.jitter
        )
        logger.debug(f"Configured rate limit for {api_name}: {config.requests_per_second}/s")
    
    def _get_bucket(self, api_name: str) -> TokenBucket:
        """Get or create bucket for API"""
        if api_name not in self._buckets:
            config = self.DEFAULT_LIMITS.get(api_name, self.DEFAULT_LIMITS["default"])
            self.configure(api_name, config)
        return self._buckets[api_name]
    
    def _get_stats(self, api_name: str) -> RateLimitStats:
        """Get stats for API"""
        if api_name not in self._stats:
            self._stats[api_name] = RateLimitStats()
        return self._stats[api_name]
    
    async def acquire(self, api_name: str, tokens: int = 1) -> float:
        """
        Acquire rate limit tokens
        
        Returns: Time waited in seconds
        """
        bucket = self._get_bucket(api_name)
        stats = self._get_stats(api_name)
        
        wait_time = await bucket.acquire(tokens)
        
        stats.total_requests += 1
        if wait_time > 0:
            stats.rate_limited += 1
            stats.avg_wait_time = (
                stats.avg_wait_time * 0.9 + wait_time * 0.1
            )
        
        return wait_time
    
    async def execute_with_retry(
        self,
        api_name: str,
        func: Callable[[], T],
        max_retries: Optional[int] = None
    ) -> T:
        """
        Execute function with rate limiting and retry
        
        Args:
            api_name: API identifier
            func: Async function to execute
            max_retries: Override max retries
        """
        config = self._configs.get(api_name, self.DEFAULT_LIMITS["default"])
        retries = max_retries or config.max_retries
        stats = self._get_stats(api_name)
        backoff = self._backoffs.get(api_name, ExponentialBackoff())
        
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                # Wait for rate limit
                await self.acquire(api_name)
                
                # Execute
                result = await func()
                
                # Success - reset backoff
                backoff.reset()
                stats.successful_requests += 1
                
                return result
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if rate limited
                is_rate_limit = any(x in error_str for x in [
                    "429", "rate limit", "too many requests",
                    "quota exceeded", "throttle"
                ])
                
                if is_rate_limit:
                    stats.rate_limited += 1
                    delay = backoff.next_delay()
                    logger.warning(
                        f"{api_name} rate limited, retry {attempt + 1}/{retries} "
                        f"in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                    stats.retries += 1
                    
                elif attempt < retries:
                    # Other errors - shorter backoff
                    delay = backoff.next_delay() / 2
                    logger.warning(
                        f"{api_name} error: {e}, retry {attempt + 1}/{retries}"
                    )
                    await asyncio.sleep(delay)
                    stats.retries += 1
                else:
                    raise
        
        raise last_error
    
    def get_stats(self, api_name: str = None) -> Dict[str, RateLimitStats]:
        """Get rate limit statistics"""
        if api_name:
            return {api_name: self._get_stats(api_name)}
        return dict(self._stats)
    
    def reset_stats(self, api_name: str = None):
        """Reset statistics"""
        if api_name and api_name in self._stats:
            self._stats[api_name] = RateLimitStats()
        else:
            for name in self._stats:
                self._stats[name] = RateLimitStats()


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limited(api_name: str):
    """
    Decorator for rate-limited functions
    
    Usage:
        @rate_limited("jupiter")
        async def get_price(mint: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await rate_limiter.execute_with_retry(
                api_name,
                lambda: func(*args, **kwargs)
            )
        return wrapper
    return decorator


# Convenience function
async def with_rate_limit(api_name: str, func: Callable[[], T]) -> T:
    """Execute function with rate limiting"""
    return await rate_limiter.execute_with_retry(api_name, func)
