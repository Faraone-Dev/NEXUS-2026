"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    NEXUS AI - Backtest Runner                                 ║
║              Test strategies on historical data before going live             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Usage:
    python run_backtest.py
    
This script allows you to:
1. Test AI strategies on historical data
2. Calculate performance metrics (Sharpe, Drawdown, Win Rate)
3. Generate detailed reports
4. Optimize parameters before live trading
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import random

from loguru import logger
from backtesting import (
    BacktestEngine,
    BacktestConfig,
    BacktestStrategy,
    SimpleMAStrategy,
    TradeSignal,
    HistoricalCandle,
    HistoricalDataLoader
)

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    level="INFO"
)


class NexusAIStrategy(BacktestStrategy):
    """
    Strategy that mimics NEXUS AI logic
    
    Combines:
    - Volume analysis
    - Price momentum
    - Risk assessment
    """
    
    def __init__(
        self,
        volume_threshold: float = 1.5,
        momentum_period: int = 5,
        risk_tolerance: float = 0.7
    ):
        super().__init__("NEXUS_AI")
        self.volume_threshold = volume_threshold
        self.momentum_period = momentum_period
        self.risk_tolerance = risk_tolerance
        
        # Internal state
        self._price_history: dict = {}
        self._volume_history: dict = {}
    
    async def generate_signals(
        self,
        timestamp: datetime,
        current_data: dict,
        engine: BacktestEngine
    ) -> list:
        """Generate signals based on NEXUS-like logic"""
        signals = []
        
        for token, candle in current_data.items():
            # Update history
            if token not in self._price_history:
                self._price_history[token] = []
                self._volume_history[token] = []
            
            self._price_history[token].append(candle.close)
            self._volume_history[token].append(candle.volume)
            
            # Keep limited history
            self._price_history[token] = self._price_history[token][-20:]
            self._volume_history[token] = self._volume_history[token][-20:]
            
            prices = self._price_history[token]
            volumes = self._volume_history[token]
            
            if len(prices) < self.momentum_period + 1:
                continue
            
            # Calculate indicators
            momentum = (prices[-1] / prices[-self.momentum_period] - 1) * 100
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 0
            volume_ratio = candle.volume / avg_volume if avg_volume > 0 else 1
            
            # Calculate confidence
            confidence = 0.5
            
            # Volume spike
            if volume_ratio > self.volume_threshold:
                confidence += 0.15
            
            # Positive momentum
            if momentum > 2:
                confidence += 0.1
            elif momentum > 5:
                confidence += 0.2
            
            # Price above recent average
            recent_avg = sum(prices[-5:]) / 5 if len(prices) >= 5 else prices[-1]
            if candle.close > recent_avg:
                confidence += 0.1
            
            # Risk check - volatility
            if len(prices) >= 5:
                high_low_range = (max(prices[-5:]) - min(prices[-5:])) / min(prices[-5:])
                if high_low_range < 0.1:  # Low volatility
                    confidence += 0.05
                elif high_low_range > 0.3:  # High volatility
                    confidence -= 0.1
            
            # Generate signal
            if confidence >= self.risk_tolerance and token not in engine.open_positions:
                signals.append(TradeSignal(
                    token=token,
                    action="buy",
                    confidence=confidence,
                    stop_loss_pct=0.10,  # 10% SL
                    take_profit_pct=0.25,  # 25% TP
                    metadata={"momentum": momentum, "volume_ratio": volume_ratio}
                ))
            
            # Exit signal - momentum reversal
            elif token in engine.open_positions:
                if momentum < -3 or volume_ratio > 2 and momentum < 0:
                    signals.append(TradeSignal(
                        token=token,
                        action="sell",
                        confidence=0.7
                    ))
        
        return signals


def generate_synthetic_data(
    num_tokens: int = 3,
    num_candles: int = 1000,
    volatility: float = 0.02
) -> dict:
    """Generate synthetic price data for testing"""
    
    tokens = [f"TOKEN_{i}" for i in range(num_tokens)]
    data = {}
    
    for token in tokens:
        candles = []
        price = random.uniform(0.001, 0.1)  # Random starting price
        base_volume = random.uniform(10000, 100000)
        base_time = datetime(2024, 1, 1)
        
        for i in range(num_candles):
            # Random walk with trend
            trend = random.uniform(-0.001, 0.002)  # Slight upward bias
            change = random.gauss(0, volatility) + trend
            price = max(0.0001, price * (1 + change))
            
            # Volume with occasional spikes
            volume = base_volume * random.uniform(0.5, 2.0)
            if random.random() < 0.05:  # 5% chance of volume spike
                volume *= random.uniform(3, 10)
            
            candles.append(HistoricalCandle(
                timestamp=base_time + timedelta(minutes=15 * i),
                open=price * random.uniform(0.99, 1.01),
                high=price * random.uniform(1.001, 1.03),
                low=price * random.uniform(0.97, 0.999),
                close=price,
                volume=volume
            ))
        
        data[token] = candles
    
    return data


async def run_backtest():
    """Run backtest with multiple strategies"""
    
    print("\n")
    print("╔" + "═" * 70 + "╗")
    print("║" + "NEXUS AI - Backtest Runner".center(70) + "║")
    print("╚" + "═" * 70 + "╝")
    
    # Generate synthetic data
    print("\n📊 Generating synthetic price data...")
    historical_data = generate_synthetic_data(
        num_tokens=3,
        num_candles=2000,  # ~21 days of 15-min candles
        volatility=0.015
    )
    
    print(f"   Generated data for {len(historical_data)} tokens")
    print(f"   Candles per token: {len(list(historical_data.values())[0])}")
    
    # Test multiple strategies
    strategies = [
        ("Simple MA (10/30)", SimpleMAStrategy(fast_period=10, slow_period=30)),
        ("Simple MA (5/20)", SimpleMAStrategy(fast_period=5, slow_period=20)),
        ("NEXUS AI (Conservative)", NexusAIStrategy(risk_tolerance=0.75)),
        ("NEXUS AI (Aggressive)", NexusAIStrategy(risk_tolerance=0.6)),
    ]
    
    results = []
    
    for name, strategy in strategies:
        print(f"\n🚀 Testing: {name}")
        
        config = BacktestConfig(
            initial_capital=10000,
            position_size_percent=0.03,  # 3% per trade
            max_positions=3,
            slippage_percent=0.002,
            trading_fee_percent=0.001
        )
        
        engine = BacktestEngine(config)
        metrics = await engine.run_backtest(historical_data, strategy)
        
        results.append((name, metrics))
        
        print(f"   Trades: {metrics.total_trades}")
        print(f"   Win Rate: {metrics.win_rate:.1%}")
        print(f"   Total P&L: ${metrics.total_pnl:,.2f} ({metrics.total_pnl_percent:+.1f}%)")
        print(f"   Sharpe: {metrics.sharpe_ratio:.2f}")
        print(f"   Max DD: {metrics.max_drawdown_percent:.1f}%")
    
    # Summary comparison
    print("\n")
    print("═" * 80)
    print("📈 STRATEGY COMPARISON")
    print("═" * 80)
    print(f"{'Strategy':<30} {'Trades':>8} {'Win Rate':>10} {'P&L %':>10} {'Sharpe':>8} {'Max DD':>8}")
    print("-" * 80)
    
    for name, m in sorted(results, key=lambda x: x[1].sharpe_ratio, reverse=True):
        print(f"{name:<30} {m.total_trades:>8} {m.win_rate:>10.1%} {m.total_pnl_percent:>+10.1f}% {m.sharpe_ratio:>8.2f} {m.max_drawdown_percent:>8.1f}%")
    
    print("═" * 80)
    
    # Winner
    best = max(results, key=lambda x: x[1].sharpe_ratio)
    print(f"\n🏆 Best Strategy: {best[0]} (Sharpe: {best[1].sharpe_ratio:.2f})")
    
    # Generate detailed report for best strategy
    print("\n" + "─" * 80)
    print("DETAILED REPORT - BEST STRATEGY")
    print("─" * 80)
    
    config = BacktestConfig(initial_capital=10000, position_size_percent=0.03, max_positions=3)
    engine = BacktestEngine(config)
    
    # Re-run best strategy
    if "NEXUS" in best[0]:
        best_strategy = NexusAIStrategy(risk_tolerance=0.75 if "Conservative" in best[0] else 0.6)
    else:
        periods = best[0].split("(")[1].rstrip(")").split("/")
        best_strategy = SimpleMAStrategy(fast_period=int(periods[0]), slow_period=int(periods[1]))
    
    metrics = await engine.run_backtest(historical_data, best_strategy)
    print(engine.generate_report(metrics))
    
    # Export trades
    export_path = Path(__file__).parent / "data_store" / "backtest_trades.json"
    engine.export_trades(str(export_path))
    print(f"\n📁 Trades exported to: {export_path}")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_backtest())
