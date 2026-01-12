# NEXUS AI Trading Bot

AI-powered crypto trading bot using DeepSeek for market analysis.

## Features

- 🤖 **AI Analysis** - DeepSeek analyzes market data and makes decisions
- 📊 **Multi-Source Data** - Price, funding, OI, sentiment, news
- 💹 **Binance Futures** - Testnet and mainnet support
- 📱 **Telegram Alerts** - Real-time notifications
- 🛡️ **Risk Management** - Auto SL/TP, position sizing
- 🧪 **Dry Run Mode** - Test without real money

## Quick Start

### 1. Install Dependencies

```bash
cd bot
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env with your keys
notepad .env
```

### 3. Get API Keys

**DeepSeek:**
1. Go to https://platform.deepseek.com/
2. Create account and get API key

**Binance Testnet (for testing):**
1. Go to https://testnet.binancefuture.com/
2. Create account and generate API keys

**Binance Live (for real trading):**
1. Go to https://www.binance.com/
2. API Management → Create API
3. Enable Futures trading

**Telegram (optional):**
1. Message @BotFather on Telegram
2. Create bot and get token
3. Get your chat ID from @userinfobot

### 4. Run Bot

```bash
# Dry run mode (default - no real trades)
python main.py

# Live trading (edit .env: DRY_RUN=false)
python main.py
```

## Configuration

Edit `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API key | required |
| `BINANCE_API_KEY` | Binance API key | required |
| `BINANCE_SECRET_KEY` | Binance secret | required |
| `BINANCE_TESTNET` | Use testnet | true |
| `TRADING_SYMBOL` | Trading pair | BTC/USDT |
| `TRADING_LEVERAGE` | Leverage | 5 |
| `POSITION_SIZE_PERCENT` | % of balance per trade | 10 |
| `STOP_LOSS_PERCENT` | Stop loss % | 2 |
| `TAKE_PROFIT_PERCENT` | Take profit % | 5 |
| `ANALYSIS_INTERVAL_SECONDS` | Seconds between analysis | 300 |
| `DRY_RUN` | Simulate trades only | true |

## Architecture

```
main.py          - Entry point, scheduler
├── config.py    - Configuration from .env
├── trader.py    - Trading logic
├── ai_engine.py - DeepSeek integration
├── exchange.py  - Binance API wrapper
├── data_fetcher.py - Market data aggregation
└── telegram_bot.py - Notifications
```

## How It Works

1. **Every N seconds** (ANALYSIS_INTERVAL):
   - Fetch price, volume, funding, OI from Binance
   - Calculate RSI, MACD, EMA indicators
   - Fetch Fear & Greed index
   - Fetch latest crypto news
   
2. **Send to DeepSeek AI**:
   - All data formatted as prompt
   - AI returns: LONG / SHORT / WAIT
   - Plus confidence %, reasoning, SL/TP levels

3. **Execute if conditions met**:
   - Confidence > 70%
   - Not already in same direction
   - Under max positions limit
   
4. **Risk Management**:
   - Auto set stop loss and take profit
   - Position size based on balance %
   - Max positions limit

## Safety

⚠️ **START WITH TESTNET** - Always test on Binance testnet first

⚠️ **DRY_RUN=true** - Default mode, no real trades

⚠️ **SMALL SIZE** - Start with small position sizes

⚠️ **MONITOR** - Check Telegram alerts and logs

## Logs

Logs are saved to `logs/` folder, rotated daily.

```bash
# View live logs
tail -f logs/nexus_2026-01-11.log
```

## Troubleshooting

**"DEEPSEEK_API_KEY is required"**
- Add your DeepSeek API key to .env

**"Could not get current price"**
- Check Binance API keys
- Check internet connection

**"Confidence too low"**
- AI is uncertain, no trade executed
- This is normal, wait for better setup

## Disclaimer

This bot is for educational purposes. Trading crypto involves significant risk. Never trade with money you can't afford to lose.
