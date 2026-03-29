# Training Data Directory

This folder contains training/backtesting data for the NEXUS AI learning engine.

## Structure

```
training/
├── historical/          # Historical token data for backtesting
│   └── tokens_YYYY-MM.json
├── patterns/            # Detected winning/losing patterns
│   └── patterns.json
├── models/              # Saved model parameters (if using ML)
│   └── weights.json
└── reports/             # Training/backtesting reports
    └── report_YYYY-MM-DD.md
```

## Data Format

### Token Historical Data
```json
{
    "mint": "...",
    "symbol": "TOKEN",
    "timestamp": "2026-01-13T12:00:00",
    "price": 0.001,
    "liquidity": 50000,
    "volume_24h": 10000,
    "holders": 500,
    "outcome_1h": 0.0012,
    "outcome_24h": 0.0015,
    "was_rug": false
}
```

## Usage

The learning engine (`ai/learning.py`) uses this data to:
1. Find patterns in winning trades
2. Optimize entry/exit parameters
3. Improve AI prompt context
