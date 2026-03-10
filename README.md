# 🤖 NEXUS AI — Autonomous Trading Engine

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.20-363636?style=for-the-badge&logo=solidity)](https://soliditylang.org)
[![DeepSeek](https://img.shields.io/badge/DeepSeek-AI_Engine-00B4D8?style=for-the-badge)](https://platform.deepseek.com)
[![Binance](https://img.shields.io/badge/Binance-Futures-F0B90B?style=for-the-badge&logo=binance)](https://binance.com)
[![License](https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge)](LICENSE)

> **AI-driven crypto trading system with LLM market analysis, multi-source data aggregation, and on-chain token-gated access tiers.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NEXUS ECOSYSTEM                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │   WEBSITE    │    │   $NEXUS     │    │   AI TRADING BOT      │  │
│  │   Landing    │───▶│   ERC-20     │───▶│   DeepSeek Engine     │  │
│  │   + Docs     │    │   Token      │    │   Binance Futures     │  │
│  └──────────────┘    └──────────────┘    └───────────────────────┘  │
│                            │                       │                │
│                            ▼                       ▼                │
│                    ┌──────────────┐    ┌───────────────────────┐    │
│                    │   Staking    │    │   Multi-Source Data    │    │
│                    │   Rewards    │    │   Price · OI · Funding │    │
│                    │   + Tiers    │    │   Sentiment · News     │    │
│                    └──────────────┘    └───────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### AI Trading Bot — `bot/`

The core engine. Runs autonomous analysis cycles using DeepSeek as the decision layer.

| Module | Purpose |
|--------|---------|
| `main.py` | Entry point — scheduler, lifecycle, signal handling |
| `ai_engine.py` | DeepSeek integration — structured JSON decisions (LONG/SHORT/WAIT) |
| `trader.py` | Execution logic — position sizing, SL/TP, max position limits |
| `data_fetcher.py` | Multi-source aggregation — exchange, CoinGlass, CryptoPanic, Fear & Greed |
| `exchange.py` | CCXT wrapper — Binance Futures (testnet + mainnet), order management |
| `telegram_bot.py` | Real-time alerts — trade signals, P&L updates, error notifications |
| `token_verifier.py` | On-chain tier verification — reads $NEXUS balance for access gating |
| `config.py` | Environment-based configuration — all params via `.env` |

**Data Pipeline:**
```
Exchange (OHLCV, Ticker, Orderbook)
    + CoinGlass (Funding Rate, Open Interest, Liquidations)
    + CryptoPanic (News Sentiment)
    + Alternative.me (Fear & Greed Index)
    + Technical Indicators (RSI, MACD, Bollinger, ATR via `ta`)
          │
          ▼
    DeepSeek Analysis → JSON { decision, confidence, SL/TP, risk_level }
          │
          ▼
    Execution (confidence ≥ 70%) → Binance Futures Order
          │
          ▼
    Telegram Alert → Position Monitoring → Auto SL/TP
```

**Risk Controls:**
- Confidence threshold (skip if < 70%)
- Max concurrent positions
- Per-trade position sizing (% of balance)
- Automatic stop-loss & take-profit
- Dry run mode for paper trading
- Sell cooldown enforcement

---

### Smart Contracts — `contracts/`

**NexusToken.sol** — ERC-20 with built-in economic mechanics:

| Feature | Detail |
|---------|--------|
| Supply | 1,000,000,000 $NEXUS |
| Buy Tax | 2% → Liquidity + Staking |
| Sell Tax | 3% → Liquidity + Staking + Burn |
| Max Wallet | 2% of supply (anti-whale) |
| Max TX | 1% of supply |
| Sell Cooldown | 1 hour between sells |
| Anti-Bot | First 3 blocks blacklisted |
| Burn | Deflationary on every sell |

**NexusStaking.sol** — Stake-to-earn with tier integration:

| Feature | Detail |
|---------|--------|
| Base APY | 10% |
| Compound | Manual claim + restake |
| Early Withdraw | 10% penalty if < 7 days |
| Tier Boost | Higher stake → higher bot tier |
| Security | ReentrancyGuard + SafeERC20 |

Both contracts use OpenZeppelin 5.x (ERC20, Ownable, ReentrancyGuard, SafeERC20).

---

### Token-Gated Access Tiers

| Tier | $NEXUS Required | Bot Features |
|------|-----------------|--------------|
| Free | 0 | Telegram signals (15 min delay) |
| Bronze | 10,000 | Real-time signals + 1 trading pair |
| Silver | 50,000 | + 5 pairs + auto-trade testnet |
| Gold | 200,000 | + Unlimited pairs + auto-trade live |
| Diamond | 1,000,000 | + Private API + priority execution + VIP support |

Verification is on-chain: `token_verifier.py` reads wallet balance via RPC and maps it to tier.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| AI Engine | DeepSeek Chat API (structured JSON output) |
| Exchange | CCXT → Binance Futures (testnet / mainnet) |
| Data | CoinGlass API, CryptoPanic, Alternative.me |
| Indicators | `ta` library (RSI, MACD, Bollinger, ATR, OBV) |
| Scheduling | APScheduler (configurable interval) |
| Logging | Loguru (console + daily rotating file) |
| Alerts | Telegram Bot API |
| Contracts | Solidity 0.8.20 + OpenZeppelin 5.x |
| Deployment | Hardhat (Base, BSC, Arbitrum, Polygon, Avalanche) |
| Frontend | Vanilla HTML/CSS/JS |

---

## Quick Start

```bash
# Clone
git clone https://github.com/conditional-team/NEXUS-2026.git
cd NEXUS-2026

# Bot
cd bot
pip install -r requirements.txt
cp .env.example .env        # Add DeepSeek + Binance keys
python main.py               # Starts in dry-run mode

# Contracts
cd ../contracts
npm install
npx hardhat compile
npx hardhat run scripts/deploy.js --network base
```

---

## Project Structure

```
NEXUS-2026/
├── bot/                        # AI Trading Bot (Python)
│   ├── main.py                 # Entry point + scheduler
│   ├── ai_engine.py            # DeepSeek LLM integration
│   ├── trader.py               # Trade execution + risk management
│   ├── data_fetcher.py         # Multi-source data aggregation
│   ├── exchange.py             # CCXT Binance Futures wrapper
│   ├── telegram_bot.py         # Telegram alert system
│   ├── token_verifier.py       # On-chain tier verification
│   ├── config.py               # Environment configuration
│   └── requirements.txt        # Python dependencies
│
├── contracts/                  # Smart Contracts (Solidity)
│   ├── NexusToken.sol          # ERC-20 — taxes, anti-whale, burn
│   ├── NexusStaking.sol        # Staking — rewards, penalties, tiers
│   ├── hardhat.config.js       # Multi-chain deployment config
│   └── scripts/deploy.js       # Deployment script
│
├── website/                    # Landing Page
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── NEXUS_MASTERPLAN.md         # Internal roadmap & tokenomics
└── LICENSE                     # Proprietary
```

---

## License

Proprietary — All Rights Reserved. See [LICENSE](LICENSE).

---

<p align="center">
  <b>NEXUS AI</b> — Autonomous Intelligence for Digital Markets
</p>
