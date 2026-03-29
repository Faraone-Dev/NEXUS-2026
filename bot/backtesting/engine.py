"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     NEXUS AI - Backtesting Engine                             ║
║          Historical performance validation & strategy testing                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import math
from loguru import logger


class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class HistoricalCandle:
    """OHLCV candle data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class BacktestTrade:
    """Single trade in backtest"""
    id: str
    token: str
    direction: TradeDirection
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    size: float = 1.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    exit_reason: str = ""
    ai_confidence: float = 0.0
    
    @property
    def is_closed(self) -> bool:
        return self.exit_time is not None
    
    @property
    def is_winner(self) -> bool:
        return self.pnl > 0


@dataclass
class BacktestConfig:
    """Backtesting configuration"""
    initial_capital: float = 10000.0
    position_size_percent: float = 0.02  # 2% per trade
    max_positions: int = 5
    slippage_percent: float = 0.001  # 0.1%
    trading_fee_percent: float = 0.001  # 0.1%
    use_stop_loss: bool = True
    default_stop_loss_percent: float = 0.05  # 5%
    use_take_profit: bool = True
    default_take_profit_percent: float = 0.10  # 10%
    timeframe_minutes: int = 15
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    # Basic stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # PnL
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Risk metrics
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    calmar_ratio: float = 0.0
    
    # Timing
    avg_trade_duration_hours: float = 0.0
    avg_bars_in_trade: int = 0
    
    # Capital
    initial_capital: float = 0.0
    final_capital: float = 0.0
    peak_capital: float = 0.0
    
    # Consistency
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # Daily/Monthly
    best_day_pnl: float = 0.0
    worst_day_pnl: float = 0.0
    avg_daily_pnl: float = 0.0


class EquityCurve:
    """Track equity over time"""
    
    def __init__(self, initial_capital: float):
        self.initial = initial_capital
        self.current = initial_capital
        self.peak = initial_capital
        self.history: List[Tuple[datetime, float]] = []
        self.drawdowns: List[float] = []
    
    def update(self, timestamp: datetime, equity: float):
        """Update equity curve"""
        self.current = equity
        self.history.append((timestamp, equity))
        
        if equity > self.peak:
            self.peak = equity
        
        drawdown = (self.peak - equity) / self.peak if self.peak > 0 else 0
        self.drawdowns.append(drawdown)
    
    def get_max_drawdown(self) -> Tuple[float, float]:
        """Get maximum drawdown (absolute and percent)"""
        if not self.drawdowns:
            return 0.0, 0.0
        max_dd_pct = max(self.drawdowns)
        max_dd_abs = max_dd_pct * self.peak
        return max_dd_abs, max_dd_pct
    
    def get_returns(self) -> List[float]:
        """Get daily returns for metrics calculation"""
        if len(self.history) < 2:
            return []
        
        returns = []
        for i in range(1, len(self.history)):
            prev = self.history[i-1][1]
            curr = self.history[i][1]
            if prev > 0:
                returns.append((curr - prev) / prev)
        return returns


class BacktestEngine:
    """
    Main Backtesting Engine
    
    Features:
    - Historical data simulation
    - Position management
    - Performance metrics calculation
    - Strategy validation
    """
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.trades: List[BacktestTrade] = []
        self.open_positions: Dict[str, BacktestTrade] = {}
        self.equity = EquityCurve(self.config.initial_capital)
        self.capital = self.config.initial_capital
        self._trade_counter = 0
        
        logger.info(f"Backtest engine initialized with ${self.config.initial_capital}")
    
    def reset(self):
        """Reset engine for new backtest"""
        self.trades.clear()
        self.open_positions.clear()
        self.equity = EquityCurve(self.config.initial_capital)
        self.capital = self.config.initial_capital
        self._trade_counter = 0
    
    async def run_backtest(
        self,
        historical_data: Dict[str, List[HistoricalCandle]],
        strategy: 'BacktestStrategy'
    ) -> PerformanceMetrics:
        """
        Run backtest on historical data
        
        Args:
            historical_data: Dict of token -> candles
            strategy: Strategy to test
            
        Returns:
            Performance metrics
        """
        self.reset()
        
        # Get all timestamps across all tokens
        all_timestamps = set()
        for candles in historical_data.values():
            for c in candles:
                all_timestamps.add(c.timestamp)
        
        sorted_timestamps = sorted(all_timestamps)
        
        logger.info(f"Running backtest: {len(sorted_timestamps)} bars, {len(historical_data)} tokens")
        
        for timestamp in sorted_timestamps:
            # Get current candles for all tokens
            current_data = {}
            for token, candles in historical_data.items():
                candle = next((c for c in candles if c.timestamp == timestamp), None)
                if candle:
                    current_data[token] = candle
            
            # Update open positions
            await self._update_positions(timestamp, current_data)
            
            # Generate signals
            signals = await strategy.generate_signals(timestamp, current_data, self)
            
            # Execute signals
            for signal in signals:
                await self._execute_signal(signal, timestamp, current_data)
            
            # Update equity
            self._update_equity(timestamp, current_data)
        
        # Close remaining positions
        await self._close_all_positions(sorted_timestamps[-1], current_data)
        
        # Calculate metrics
        metrics = self._calculate_metrics()
        
        logger.info(f"Backtest complete: {metrics.total_trades} trades, {metrics.win_rate:.1%} win rate")
        
        return metrics
    
    async def _update_positions(
        self,
        timestamp: datetime,
        current_data: Dict[str, HistoricalCandle]
    ):
        """Check and update open positions"""
        positions_to_close = []
        
        for token, trade in self.open_positions.items():
            if token not in current_data:
                continue
            
            candle = current_data[token]
            
            # Check stop loss
            if trade.stop_loss and candle.low <= trade.stop_loss:
                trade.exit_price = trade.stop_loss
                trade.exit_reason = "stop_loss"
                positions_to_close.append(token)
                continue
            
            # Check take profit
            if trade.take_profit and candle.high >= trade.take_profit:
                trade.exit_price = trade.take_profit
                trade.exit_reason = "take_profit"
                positions_to_close.append(token)
                continue
        
        # Close positions
        for token in positions_to_close:
            await self._close_position(token, timestamp)
    
    async def _execute_signal(
        self,
        signal: 'TradeSignal',
        timestamp: datetime,
        current_data: Dict[str, HistoricalCandle]
    ):
        """Execute a trade signal"""
        if signal.token not in current_data:
            return
        
        candle = current_data[signal.token]
        
        if signal.action == "buy" and signal.token not in self.open_positions:
            # Check max positions
            if len(self.open_positions) >= self.config.max_positions:
                return
            
            # Calculate position size
            position_value = self.capital * self.config.position_size_percent
            entry_price = candle.close * (1 + self.config.slippage_percent)
            size = position_value / entry_price
            
            # Apply trading fee
            fee = position_value * self.config.trading_fee_percent
            self.capital -= fee
            
            # Create trade
            self._trade_counter += 1
            trade = BacktestTrade(
                id=f"BT-{self._trade_counter:06d}",
                token=signal.token,
                direction=TradeDirection.LONG,
                entry_time=timestamp,
                entry_price=entry_price,
                size=size,
                ai_confidence=signal.confidence
            )
            
            # Set SL/TP
            if self.config.use_stop_loss:
                sl_pct = signal.stop_loss_pct or self.config.default_stop_loss_percent
                trade.stop_loss = entry_price * (1 - sl_pct)
            
            if self.config.use_take_profit:
                tp_pct = signal.take_profit_pct or self.config.default_take_profit_percent
                trade.take_profit = entry_price * (1 + tp_pct)
            
            self.open_positions[signal.token] = trade
            
        elif signal.action == "sell" and signal.token in self.open_positions:
            trade = self.open_positions[signal.token]
            trade.exit_price = candle.close * (1 - self.config.slippage_percent)
            trade.exit_reason = "signal"
            await self._close_position(signal.token, timestamp)
    
    async def _close_position(self, token: str, timestamp: datetime):
        """Close a position and calculate PnL"""
        if token not in self.open_positions:
            return
        
        trade = self.open_positions.pop(token)
        trade.exit_time = timestamp
        
        # Calculate PnL
        if trade.exit_price:
            gross_pnl = (trade.exit_price - trade.entry_price) * trade.size
            fee = abs(gross_pnl) * self.config.trading_fee_percent
            trade.pnl = gross_pnl - fee
            trade.pnl_percent = (trade.exit_price / trade.entry_price - 1) * 100
            
            self.capital += trade.pnl + (trade.entry_price * trade.size)
        
        self.trades.append(trade)
    
    async def _close_all_positions(
        self,
        timestamp: datetime,
        current_data: Dict[str, HistoricalCandle]
    ):
        """Close all remaining positions"""
        for token in list(self.open_positions.keys()):
            if token in current_data:
                trade = self.open_positions[token]
                trade.exit_price = current_data[token].close
                trade.exit_reason = "backtest_end"
                await self._close_position(token, timestamp)
    
    def _update_equity(
        self,
        timestamp: datetime,
        current_data: Dict[str, HistoricalCandle]
    ):
        """Update equity curve"""
        # Calculate unrealized PnL
        unrealized = 0.0
        for token, trade in self.open_positions.items():
            if token in current_data:
                current_price = current_data[token].close
                unrealized += (current_price - trade.entry_price) * trade.size
        
        total_equity = self.capital + unrealized
        self.equity.update(timestamp, total_equity)
    
    def _calculate_metrics(self) -> PerformanceMetrics:
        """Calculate all performance metrics"""
        metrics = PerformanceMetrics()
        metrics.initial_capital = self.config.initial_capital
        metrics.final_capital = self.capital
        metrics.peak_capital = self.equity.peak
        
        if not self.trades:
            return metrics
        
        # Basic stats
        metrics.total_trades = len(self.trades)
        winners = [t for t in self.trades if t.pnl > 0]
        losers = [t for t in self.trades if t.pnl <= 0]
        
        metrics.winning_trades = len(winners)
        metrics.losing_trades = len(losers)
        metrics.win_rate = len(winners) / len(self.trades) if self.trades else 0
        
        # PnL
        pnls = [t.pnl for t in self.trades]
        metrics.total_pnl = sum(pnls)
        metrics.total_pnl_percent = (self.capital / self.config.initial_capital - 1) * 100
        
        if winners:
            win_pnls = [t.pnl for t in winners]
            metrics.avg_win = sum(win_pnls) / len(win_pnls)
            metrics.largest_win = max(win_pnls)
        
        if losers:
            loss_pnls = [t.pnl for t in losers]
            metrics.avg_loss = sum(loss_pnls) / len(loss_pnls)
            metrics.largest_loss = min(loss_pnls)
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winners) if winners else 0
        gross_loss = abs(sum(t.pnl for t in losers)) if losers else 0
        metrics.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Drawdown
        dd_abs, dd_pct = self.equity.get_max_drawdown()
        metrics.max_drawdown = dd_abs
        metrics.max_drawdown_percent = dd_pct * 100
        
        # Sharpe & Sortino
        returns = self.equity.get_returns()
        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = self._std_dev(returns)
            
            # Annualized (assuming 15-min bars, ~35040 per year)
            bars_per_year = 365 * 24 * 4
            
            if std_return > 0:
                metrics.sharpe_ratio = (avg_return * math.sqrt(bars_per_year)) / std_return
            
            # Sortino (downside deviation)
            negative_returns = [r for r in returns if r < 0]
            if negative_returns:
                downside_std = self._std_dev(negative_returns)
                if downside_std > 0:
                    metrics.sortino_ratio = (avg_return * math.sqrt(bars_per_year)) / downside_std
        
        # Calmar ratio
        if metrics.max_drawdown_percent > 0:
            annual_return = metrics.total_pnl_percent  # Simplified
            metrics.calmar_ratio = annual_return / metrics.max_drawdown_percent
        
        # Trade duration
        durations = []
        for t in self.trades:
            if t.exit_time and t.entry_time:
                duration = (t.exit_time - t.entry_time).total_seconds() / 3600
                durations.append(duration)
        if durations:
            metrics.avg_trade_duration_hours = sum(durations) / len(durations)
        
        # Consecutive wins/losses
        current_streak = 0
        is_winning_streak = True
        
        for trade in self.trades:
            if trade.pnl > 0:
                if is_winning_streak:
                    current_streak += 1
                else:
                    current_streak = 1
                    is_winning_streak = True
                metrics.max_consecutive_wins = max(metrics.max_consecutive_wins, current_streak)
            else:
                if not is_winning_streak:
                    current_streak += 1
                else:
                    current_streak = 1
                    is_winning_streak = False
                metrics.max_consecutive_losses = max(metrics.max_consecutive_losses, current_streak)
        
        return metrics
    
    def _std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)
    
    def export_trades(self, filepath: str):
        """Export trades to JSON"""
        data = []
        for trade in self.trades:
            d = asdict(trade)
            d['direction'] = trade.direction.value
            d['entry_time'] = trade.entry_time.isoformat() if trade.entry_time else None
            d['exit_time'] = trade.exit_time.isoformat() if trade.exit_time else None
            data.append(d)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported {len(data)} trades to {filepath}")
    
    def generate_report(self, metrics: PerformanceMetrics) -> str:
        """Generate text report"""
        report = f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    NEXUS AI BACKTEST REPORT                          ║
╚══════════════════════════════════════════════════════════════════════╝

📊 SUMMARY
─────────────────────────────────────────────────────────────
Initial Capital:     ${metrics.initial_capital:,.2f}
Final Capital:       ${metrics.final_capital:,.2f}
Total P&L:           ${metrics.total_pnl:,.2f} ({metrics.total_pnl_percent:+.2f}%)

📈 TRADES
─────────────────────────────────────────────────────────────
Total Trades:        {metrics.total_trades}
Winners:             {metrics.winning_trades} ({metrics.win_rate:.1%})
Losers:              {metrics.losing_trades}
Avg Win:             ${metrics.avg_win:,.2f}
Avg Loss:            ${metrics.avg_loss:,.2f}
Largest Win:         ${metrics.largest_win:,.2f}
Largest Loss:        ${metrics.largest_loss:,.2f}
Profit Factor:       {metrics.profit_factor:.2f}

⚠️ RISK METRICS
─────────────────────────────────────────────────────────────
Max Drawdown:        ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_percent:.2f}%)
Sharpe Ratio:        {metrics.sharpe_ratio:.2f}
Sortino Ratio:       {metrics.sortino_ratio:.2f}
Calmar Ratio:        {metrics.calmar_ratio:.2f}

🎯 CONSISTENCY
─────────────────────────────────────────────────────────────
Max Consecutive Wins:    {metrics.max_consecutive_wins}
Max Consecutive Losses:  {metrics.max_consecutive_losses}
Avg Trade Duration:      {metrics.avg_trade_duration_hours:.1f} hours

═══════════════════════════════════════════════════════════════════════
"""
        return report


@dataclass
class TradeSignal:
    """Signal from strategy"""
    token: str
    action: str  # buy, sell, hold
    confidence: float = 0.0
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BacktestStrategy:
    """
    Base class for backtesting strategies
    
    Override generate_signals to implement your strategy
    """
    
    def __init__(self, name: str = "BaseStrategy"):
        self.name = name
    
    async def generate_signals(
        self,
        timestamp: datetime,
        current_data: Dict[str, HistoricalCandle],
        engine: BacktestEngine
    ) -> List[TradeSignal]:
        """
        Generate trade signals
        
        Override this in your strategy
        """
        return []


class SimpleMAStrategy(BacktestStrategy):
    """
    Example: Simple Moving Average Crossover Strategy
    """
    
    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        super().__init__("MA_Crossover")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self._price_history: Dict[str, List[float]] = {}
    
    async def generate_signals(
        self,
        timestamp: datetime,
        current_data: Dict[str, HistoricalCandle],
        engine: BacktestEngine
    ) -> List[TradeSignal]:
        signals = []
        
        for token, candle in current_data.items():
            # Update price history
            if token not in self._price_history:
                self._price_history[token] = []
            self._price_history[token].append(candle.close)
            
            # Keep only what we need
            self._price_history[token] = self._price_history[token][-self.slow_period:]
            
            prices = self._price_history[token]
            if len(prices) < self.slow_period:
                continue
            
            # Calculate MAs
            fast_ma = sum(prices[-self.fast_period:]) / self.fast_period
            slow_ma = sum(prices) / self.slow_period
            
            # Previous MAs (for crossover detection)
            if len(prices) > 1:
                prev_prices = prices[:-1]
                prev_fast = sum(prev_prices[-self.fast_period:]) / self.fast_period if len(prev_prices) >= self.fast_period else fast_ma
                prev_slow = sum(prev_prices[-self.slow_period:]) / len(prev_prices[-self.slow_period:])
                
                # Golden cross (buy)
                if prev_fast <= prev_slow and fast_ma > slow_ma:
                    signals.append(TradeSignal(
                        token=token,
                        action="buy",
                        confidence=0.7,
                        stop_loss_pct=0.05,
                        take_profit_pct=0.15
                    ))
                
                # Death cross (sell)
                elif prev_fast >= prev_slow and fast_ma < slow_ma:
                    signals.append(TradeSignal(
                        token=token,
                        action="sell",
                        confidence=0.7
                    ))
        
        return signals


class HistoricalDataLoader:
    """Load historical data for backtesting"""
    
    def __init__(self, db_path: str = "backtest_data.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY,
                token TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                UNIQUE(token, timestamp)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_candles_token_time 
            ON candles(token, timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    async def save_candles(self, token: str, candles: List[HistoricalCandle]):
        """Save candles to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for c in candles:
            cursor.execute("""
                INSERT OR REPLACE INTO candles 
                (token, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (token, c.timestamp.isoformat(), c.open, c.high, c.low, c.close, c.volume))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(candles)} candles for {token}")
    
    async def load_candles(
        self,
        token: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[HistoricalCandle]:
        """Load candles from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT timestamp, open, high, low, close, volume FROM candles WHERE token = ?"
        params = [token]
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY timestamp"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        candles = []
        for row in rows:
            candles.append(HistoricalCandle(
                timestamp=datetime.fromisoformat(row[0]),
                open=row[1],
                high=row[2],
                low=row[3],
                close=row[4],
                volume=row[5]
            ))
        
        logger.info(f"Loaded {len(candles)} candles for {token}")
        return candles
    
    async def get_available_tokens(self) -> List[str]:
        """Get list of tokens with data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT token FROM candles")
        tokens = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tokens
