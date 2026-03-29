"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                   NEXUS AI - Load Testing & Scalability                       ║
║          Performance benchmarks, connection pooling, async optimization       ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import time
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import aiohttp
import json
from loguru import logger


class LoadTestStatus(Enum):
    """Load test status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RequestResult:
    """Single request result"""
    success: bool
    status_code: int
    latency_ms: float
    response_size: int
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LoadTestConfig:
    """Load test configuration"""
    target_rps: int = 100                  # Requests per second
    duration_seconds: int = 60             # Test duration
    ramp_up_seconds: int = 10              # Gradual ramp up
    concurrent_users: int = 50             # Simulated concurrent users
    timeout_seconds: float = 30.0          # Request timeout
    think_time_ms: int = 100               # Time between requests per user
    max_connections: int = 100             # Connection pool size
    keep_alive: bool = True                # Keep connections alive
    endpoints: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class LoadTestMetrics:
    """Comprehensive load test metrics"""
    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Request counts
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Latency (ms)
    min_latency: float = float('inf')
    max_latency: float = 0.0
    avg_latency: float = 0.0
    median_latency: float = 0.0
    p90_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    
    # Throughput
    requests_per_second: float = 0.0
    bytes_per_second: float = 0.0
    
    # Errors
    error_rate: float = 0.0
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Status codes
    status_codes: Dict[int, int] = field(default_factory=dict)
    
    # Concurrency
    peak_concurrent: int = 0
    avg_concurrent: float = 0.0


class ConnectionPool:
    """
    Async HTTP Connection Pool
    
    Manages persistent connections for high throughput
    """
    
    def __init__(
        self,
        max_connections: int = 100,
        max_connections_per_host: int = 30,
        keepalive_timeout: int = 30,
        enable_cleanup: bool = True
    ):
        self.max_connections = max_connections
        self.max_per_host = max_connections_per_host
        self.keepalive_timeout = keepalive_timeout
        self.enable_cleanup = enable_cleanup
        
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._stats = {
            'total_requests': 0,
            'active_connections': 0,
            'peak_connections': 0,
            'reused_connections': 0
        }
    
    async def __aenter__(self):
        await self.open()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def open(self):
        """Initialize connection pool"""
        self._connector = aiohttp.TCPConnector(
            limit=self.max_connections,
            limit_per_host=self.max_per_host,
            keepalive_timeout=self.keepalive_timeout,
            enable_cleanup_closed=self.enable_cleanup,
            force_close=False
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=timeout
        )
        
        logger.info(f"Connection pool opened: {self.max_connections} max connections")
    
    async def close(self):
        """Close connection pool"""
        if self._session:
            await self._session.close()
        if self._connector:
            await self._connector.close()
        
        logger.info(f"Connection pool closed. Stats: {self._stats}")
    
    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Tuple[int, bytes, float]:
        """
        Make HTTP request using pool
        
        Returns: (status_code, response_body, latency_ms)
        """
        if not self._session:
            raise RuntimeError("Connection pool not opened")
        
        start = time.monotonic()
        self._stats['total_requests'] += 1
        self._stats['active_connections'] += 1
        self._stats['peak_connections'] = max(
            self._stats['peak_connections'],
            self._stats['active_connections']
        )
        
        try:
            async with self._session.request(method, url, **kwargs) as response:
                body = await response.read()
                latency = (time.monotonic() - start) * 1000
                return response.status, body, latency
        finally:
            self._stats['active_connections'] -= 1
    
    def get_stats(self) -> Dict[str, int]:
        """Get connection pool statistics"""
        return dict(self._stats)


class VirtualUser:
    """
    Simulates a user making requests
    """
    
    def __init__(
        self,
        user_id: int,
        pool: ConnectionPool,
        think_time_ms: int = 100
    ):
        self.user_id = user_id
        self.pool = pool
        self.think_time_ms = think_time_ms
        self.results: List[RequestResult] = []
        self._running = False
    
    async def run(
        self,
        endpoints: List[Dict[str, Any]],
        duration: float,
        ramp_delay: float = 0
    ):
        """Run virtual user for specified duration"""
        if ramp_delay > 0:
            await asyncio.sleep(ramp_delay)
        
        self._running = True
        end_time = time.monotonic() + duration
        
        while self._running and time.monotonic() < end_time:
            for endpoint in endpoints:
                if not self._running or time.monotonic() >= end_time:
                    break
                
                result = await self._make_request(endpoint)
                self.results.append(result)
                
                # Think time
                await asyncio.sleep(self.think_time_ms / 1000)
    
    async def _make_request(self, endpoint: Dict[str, Any]) -> RequestResult:
        """Make single request"""
        method = endpoint.get('method', 'GET')
        url = endpoint['url']
        headers = endpoint.get('headers', {})
        body = endpoint.get('body')
        
        try:
            status, response_body, latency = await self.pool.request(
                method=method,
                url=url,
                headers=headers,
                data=body
            )
            
            return RequestResult(
                success=200 <= status < 400,
                status_code=status,
                latency_ms=latency,
                response_size=len(response_body)
            )
            
        except asyncio.TimeoutError:
            return RequestResult(
                success=False,
                status_code=0,
                latency_ms=30000,
                response_size=0,
                error="Timeout"
            )
        except Exception as e:
            return RequestResult(
                success=False,
                status_code=0,
                latency_ms=0,
                response_size=0,
                error=str(e)
            )
    
    def stop(self):
        """Stop virtual user"""
        self._running = False


class LoadTestRunner:
    """
    Main load test orchestrator
    """
    
    def __init__(self, config: LoadTestConfig = None):
        self.config = config or LoadTestConfig()
        self.status = LoadTestStatus.PENDING
        self.metrics = LoadTestMetrics()
        self._users: List[VirtualUser] = []
        self._pool: Optional[ConnectionPool] = None
    
    async def run(self) -> LoadTestMetrics:
        """Execute load test"""
        self.status = LoadTestStatus.RUNNING
        self.metrics = LoadTestMetrics()
        self.metrics.start_time = datetime.now()
        
        logger.info(f"Starting load test: {self.config.concurrent_users} users, "
                   f"{self.config.duration_seconds}s duration")
        
        try:
            # Create connection pool
            self._pool = ConnectionPool(
                max_connections=self.config.max_connections
            )
            await self._pool.open()
            
            # Create virtual users
            self._users = [
                VirtualUser(i, self._pool, self.config.think_time_ms)
                for i in range(self.config.concurrent_users)
            ]
            
            # Calculate ramp-up delays
            ramp_interval = self.config.ramp_up_seconds / self.config.concurrent_users
            
            # Start all users
            tasks = []
            for i, user in enumerate(self._users):
                task = asyncio.create_task(
                    user.run(
                        endpoints=self.config.endpoints,
                        duration=self.config.duration_seconds,
                        ramp_delay=i * ramp_interval
                    )
                )
                tasks.append(task)
            
            # Wait for completion
            await asyncio.gather(*tasks)
            
            # Calculate metrics
            self._calculate_metrics()
            
            self.status = LoadTestStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Load test failed: {e}")
            self.status = LoadTestStatus.FAILED
            raise
        
        finally:
            if self._pool:
                await self._pool.close()
        
        return self.metrics
    
    def _calculate_metrics(self):
        """Calculate final metrics"""
        self.metrics.end_time = datetime.now()
        self.metrics.duration_seconds = (
            self.metrics.end_time - self.metrics.start_time
        ).total_seconds()
        
        # Collect all results
        all_results: List[RequestResult] = []
        for user in self._users:
            all_results.extend(user.results)
        
        if not all_results:
            return
        
        # Request counts
        self.metrics.total_requests = len(all_results)
        self.metrics.successful_requests = sum(1 for r in all_results if r.success)
        self.metrics.failed_requests = self.metrics.total_requests - self.metrics.successful_requests
        
        # Latencies
        latencies = [r.latency_ms for r in all_results if r.latency_ms > 0]
        if latencies:
            sorted_latencies = sorted(latencies)
            self.metrics.min_latency = min(latencies)
            self.metrics.max_latency = max(latencies)
            self.metrics.avg_latency = statistics.mean(latencies)
            self.metrics.median_latency = statistics.median(latencies)
            
            n = len(sorted_latencies)
            self.metrics.p90_latency = sorted_latencies[int(n * 0.90)]
            self.metrics.p95_latency = sorted_latencies[int(n * 0.95)]
            self.metrics.p99_latency = sorted_latencies[int(n * 0.99)]
        
        # Throughput
        if self.metrics.duration_seconds > 0:
            self.metrics.requests_per_second = (
                self.metrics.total_requests / self.metrics.duration_seconds
            )
            total_bytes = sum(r.response_size for r in all_results)
            self.metrics.bytes_per_second = total_bytes / self.metrics.duration_seconds
        
        # Error rate
        if self.metrics.total_requests > 0:
            self.metrics.error_rate = (
                self.metrics.failed_requests / self.metrics.total_requests
            )
        
        # Errors by type
        for r in all_results:
            if r.error:
                error_type = r.error.split(':')[0]
                self.metrics.errors_by_type[error_type] = (
                    self.metrics.errors_by_type.get(error_type, 0) + 1
                )
        
        # Status codes
        for r in all_results:
            code = r.status_code
            self.metrics.status_codes[code] = self.metrics.status_codes.get(code, 0) + 1
        
        # Concurrency
        self.metrics.peak_concurrent = self.config.concurrent_users
        
        logger.info(f"Load test complete: {self.metrics.requests_per_second:.1f} RPS, "
                   f"{self.metrics.avg_latency:.1f}ms avg latency")
    
    async def stop(self):
        """Stop running test"""
        for user in self._users:
            user.stop()
        self.status = LoadTestStatus.CANCELLED
    
    def generate_report(self) -> str:
        """Generate text report"""
        m = self.metrics
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       NEXUS AI LOAD TEST REPORT                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

📋 TEST CONFIGURATION
────────────────────────────────────────────────────────────────────────
Concurrent Users:    {self.config.concurrent_users}
Duration:            {self.config.duration_seconds}s
Target RPS:          {self.config.target_rps}
Connection Pool:     {self.config.max_connections}

📊 RESULTS SUMMARY
────────────────────────────────────────────────────────────────────────
Status:              {self.status.value.upper()}
Total Requests:      {m.total_requests:,}
Successful:          {m.successful_requests:,}
Failed:              {m.failed_requests:,}
Error Rate:          {m.error_rate:.2%}

⚡ THROUGHPUT
────────────────────────────────────────────────────────────────────────
Requests/Second:     {m.requests_per_second:.2f}
MB/Second:           {m.bytes_per_second / 1024 / 1024:.2f}

⏱️ LATENCY (ms)
────────────────────────────────────────────────────────────────────────
Min:                 {m.min_latency:.2f}
Max:                 {m.max_latency:.2f}
Average:             {m.avg_latency:.2f}
Median:              {m.median_latency:.2f}
P90:                 {m.p90_latency:.2f}
P95:                 {m.p95_latency:.2f}
P99:                 {m.p99_latency:.2f}

📈 STATUS CODES
────────────────────────────────────────────────────────────────────────
"""
        for code, count in sorted(m.status_codes.items()):
            report += f"  {code}: {count:,}\n"
        
        if m.errors_by_type:
            report += """
❌ ERRORS BY TYPE
────────────────────────────────────────────────────────────────────────
"""
            for error_type, count in m.errors_by_type.items():
                report += f"  {error_type}: {count:,}\n"
        
        report += """
══════════════════════════════════════════════════════════════════════════════
"""
        return report


class PerformanceBenchmark:
    """
    Benchmark suite for NEXUS AI components
    """
    
    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
    
    async def benchmark_function(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10
    ) -> Dict[str, float]:
        """Benchmark a single function"""
        
        # Warmup
        for _ in range(warmup):
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
        
        # Benchmark
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
        
        result = {
            'iterations': iterations,
            'min_ms': min(times),
            'max_ms': max(times),
            'avg_ms': statistics.mean(times),
            'std_ms': statistics.stdev(times) if len(times) > 1 else 0,
            'p50_ms': statistics.median(times),
            'p99_ms': sorted(times)[int(len(times) * 0.99)],
            'ops_per_sec': 1000 / statistics.mean(times)
        }
        
        self.results[name] = result
        logger.info(f"Benchmark {name}: {result['avg_ms']:.3f}ms avg, "
                   f"{result['ops_per_sec']:.1f} ops/s")
        
        return result
    
    async def run_suite(
        self,
        benchmarks: Dict[str, Callable]
    ) -> Dict[str, Dict[str, float]]:
        """Run benchmark suite"""
        
        for name, func in benchmarks.items():
            await self.benchmark_function(name, func)
        
        return self.results
    
    def generate_report(self) -> str:
        """Generate benchmark report"""
        report = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                     NEXUS AI PERFORMANCE BENCHMARKS                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

"""
        for name, result in self.results.items():
            report += f"""
{name}
────────────────────────────────────────────────────────────────────────
  Iterations:     {result['iterations']}
  Avg:            {result['avg_ms']:.3f} ms
  Min:            {result['min_ms']:.3f} ms
  Max:            {result['max_ms']:.3f} ms
  P99:            {result['p99_ms']:.3f} ms
  Ops/sec:        {result['ops_per_sec']:.1f}
"""
        
        return report


class AsyncOptimizer:
    """
    Utilities for async optimization
    """
    
    @staticmethod
    async def gather_with_concurrency(
        coros: List[Any],
        max_concurrent: int = 10
    ) -> List[Any]:
        """
        Run coroutines with limited concurrency
        
        Prevents overwhelming APIs with too many concurrent requests
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def limited(coro):
            async with semaphore:
                return await coro
        
        return await asyncio.gather(*[limited(c) for c in coros])
    
    @staticmethod
    async def batch_process(
        items: List[Any],
        processor: Callable,
        batch_size: int = 10,
        delay_between_batches: float = 0.1
    ) -> List[Any]:
        """
        Process items in batches
        
        Useful for rate-limited APIs
        """
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            batch_tasks = [processor(item) for item in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            results.extend(batch_results)
            
            if i + batch_size < len(items):
                await asyncio.sleep(delay_between_batches)
        
        return results
    
    @staticmethod
    def create_task_group():
        """Create a task group for structured concurrency"""
        return asyncio.TaskGroup() if hasattr(asyncio, 'TaskGroup') else None


# Convenience functions
async def run_load_test(
    endpoints: List[Dict[str, Any]],
    concurrent_users: int = 50,
    duration_seconds: int = 60
) -> LoadTestMetrics:
    """Quick load test"""
    config = LoadTestConfig(
        concurrent_users=concurrent_users,
        duration_seconds=duration_seconds,
        endpoints=endpoints
    )
    runner = LoadTestRunner(config)
    return await runner.run()


async def benchmark(func: Callable, iterations: int = 100) -> Dict[str, float]:
    """Quick benchmark"""
    bench = PerformanceBenchmark()
    return await bench.benchmark_function("benchmark", func, iterations)
