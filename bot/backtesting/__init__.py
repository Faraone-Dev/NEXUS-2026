# Backtesting module
from .engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestTrade,
    BacktestStrategy,
    SimpleMAStrategy,
    TradeSignal,
    PerformanceMetrics,
    HistoricalCandle,
    HistoricalDataLoader,
    EquityCurve
)

__all__ = [
    'BacktestEngine',
    'BacktestConfig',
    'BacktestTrade',
    'BacktestStrategy',
    'SimpleMAStrategy',
    'TradeSignal',
    'PerformanceMetrics',
    'HistoricalCandle',
    'HistoricalDataLoader',
    'EquityCurve'
]
