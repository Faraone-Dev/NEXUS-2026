# ◈ NEXUS AI — Solana Trading Intelligence

```
███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗     █████╗ ██╗
████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝    ██╔══██╗██║
██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗    ███████║██║
██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║    ██╔══██║██║
██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║    ██║  ██║██║
╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝ ╚══════╝    ╚═╝  ╚═╝╚═╝
```

> **AI-Powered Solana Trading Intelligence**
> 
> Multi-agent AI system that scans, validates, and trades tokens on Solana DEXs — with real-time technical analysis, on-chain risk scoring, and self-improving learning loops.

---

## 🎯 What It Does

NEXUS is a fully autonomous Solana trading system. It's not a signal channel — it's an end-to-end pipeline that:

1. **Scans** — Continuously discovers new tokens via DexScreener, Birdeye, PumpFun
2. **Validates** — Multi-layer rug detection (contract, liquidity, holders, on-chain)
3. **Analyzes** — 4 specialized DeepSeek AI agents + Aarna MCP technical analysis (44 indicators)
4. **Executes** — Auto-trades via Jupiter with position sizing and SL/TP management
5. **Learns** — Every trade outcome feeds back into reactive weight tuning
6. **Alerts** — Real-time Telegram notifications with P&L tracking

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          NEXUS AI PIPELINE                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ╔════════════════════════════════════════════════════════════════════╗  │
│   ║                     📊 DATA LAYER                                   ║  │
│   ╠════════════════════════════════════════════════════════════════════╣  │
│   ║  Jupiter API          → Swap routes, real-time prices               ║  │
│   ║  Birdeye API          → Token analytics, holder data                ║  │
│   ║  DexScreener API      → New pairs, volume, liquidity               ║  │
│   ║  Helius RPC           → On-chain data, transactions                 ║  │
│   ║  PumpFun API          → New launches, bonding curves                ║  │
│   ║  Aarna MCP            → 44 TA indicators (RSI, MACD, BB, etc.)     ║  │
│   ║  Whale Tracker        → Large wallet movements                      ║  │
│   ╚════════════════════════════════════════════════════════════════════╝  │
│                                     │                                     │
│                                     ▼                                     │
│   ╔════════════════════════════════════════════════════════════════════╗  │
│   ║                     🛡️ VALIDATION LAYER                             ║  │
│   ╠════════════════════════════════════════════════════════════════════╣  │
│   ║  RugChecker           → Mint/freeze authority, LP lock, holders     ║  │
│   ║  ContractAnalyzer     → Bytecode analysis, honeypot detection       ║  │
│   ║  SecurityScanner      → Vulnerability scan, token security check    ║  │
│   ╚════════════════════════════════════════════════════════════════════╝  │
│                                     │                                     │
│                                     ▼                                     │
│   ╔════════════════════════════════════════════════════════════════════╗  │
│   ║                     🧠 AI ANALYSIS LAYER                            ║  │
│   ╠════════════════════════════════════════════════════════════════════╣  │
│   ║  Agent #1: Token Analyzer       → Security score 0-100              ║  │
│   ║  Agent #2: Sentiment Analyzer   → Hype + social momentum            ║  │
│   ║  Agent #3: Risk Assessor        → Rug probability, red flags        ║  │
│   ║  Agent #4: Master Decision      → BUY/SELL/WAIT + TA integration    ║  │
│   ╚════════════════════════════════════════════════════════════════════╝  │
│                                     │                                     │
│                                     ▼                                     │
│   ╔════════════════════════════════════════════════════════════════════╗  │
│   ║                     📈 LEARNING LAYER                               ║  │
│   ╠════════════════════════════════════════════════════════════════════╣  │
│   ║  ReactiveAI           → Per-signal weight tuning from outcomes      ║  │
│   ║  LearningEngine       → AI-driven trade post-mortems (24h cycle)    ║  │
│   ║  SQLite Database      → Full trade history, scans, whale alerts     ║  │
│   ╚════════════════════════════════════════════════════════════════════╝  │
│                                     │                                     │
│                                     ▼                                     │
│   ╔════════════════════════════════════════════════════════════════════╗  │
│   ║                     💰 EXECUTION LAYER                              ║  │
│   ╠════════════════════════════════════════════════════════════════════╣  │
│   ║  Jupiter Swap         → Best-route execution, slippage control      ║  │
│   ║  Position Manager     → Multi-position tracking, auto SL/TP        ║  │
│   ║  Simulator            → Paper trading with real mainnet prices      ║  │
│   ╚════════════════════════════════════════════════════════════════════╝  │
│                                     │                                     │
│                                     ▼                                     │
│   ╔════════════════════════════════════════════════════════════════════╗  │
│   ║                     🔔 ALERTS                                       ║  │
│   ╠════════════════════════════════════════════════════════════════════╣  │
│   ║  Telegram Bot         → Trade signals, P&L reports, whale alerts    ║  │
│   ╚════════════════════════════════════════════════════════════════════╝  │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
nexus-ai/
│
├── bot/                              # AI Trading Bot
│   ├── main.py                       # Entry point — scan loop, trade pipeline
│   ├── api_server.py                 # Dashboard REST API (aiohttp, port 8080)
│   ├── config.py                     # Centralized config from .env
│   ├── run_backtest.py               # Backtesting runner
│   │
│   ├── ai/                           # AI Layer
│   │   ├── engine.py                 # DeepSeek client (OpenAI-compatible)
│   │   ├── agents.py                 # 4 specialized agents + decision model
│   │   ├── learning.py               # Post-mortem analysis, parameter tuning
│   │   ├── reactive.py               # Reactive weight system (per-signal)
│   │   └── rule_scorer.py            # Deterministic rule-based scorer (A/B baseline)
│   │
│   ├── data/                         # Data Layer
│   │   ├── jupiter.py                # Jupiter V3 — prices, quotes, swaps
│   │   ├── birdeye.py                # Birdeye — token analytics, holders
│   │   ├── dexscreener.py            # DexScreener — new pairs, volume
│   │   ├── helius.py                 # Helius — on-chain data, RPC
│   │   ├── pumpfun.py                # PumpFun — new token launches
│   │   ├── rugcheck.py               # RugCheck API integration
│   │   ├── aarna_signals.py          # Aarna MCP — 44 TA indicators via Smithery
│   │   ├── whale_tracker.py          # Whale wallet monitoring
│   │   ├── scan_updater.py           # Background scan refresh
│   │   └── database.py               # SQLite — trades, scans, whale alerts
│   │
│   ├── validation/                   # Validation Layer
│   │   ├── rug_checker.py            # Multi-source rug detection
│   │   └── contract_analyzer.py      # Smart contract security analysis
│   │
│   ├── execution/                    # Execution Layer
│   │   ├── jupiter_swap.py           # Swap execution via Jupiter
│   │   ├── position_manager.py       # Position tracking, SL/TP management
│   │   └── simulator.py              # Paper trading engine
│   │
│   ├── core/                         # Infrastructure
│   │   ├── rate_limiter.py           # Token bucket rate limiting
│   │   ├── circuit_breaker.py        # Circuit breaker + health monitoring
│   │   ├── resilient_client.py       # Retry-aware HTTP client
│   │   └── load_testing.py           # Performance benchmarking
│   │
│   ├── security/                     # Security
│   │   └── audit.py                  # Token security scanner, vuln detection
│   │
│   ├── telegram/                     # Telegram Integration
│   │   ├── bot.py                    # Bot commands and handlers
│   │   └── alerts.py                 # Trade alerts, P&L notifications
│   │
│   ├── backtesting/                  # Backtesting Engine
│   │   └── engine.py                 # Historical simulation framework
│   │
│   ├── tests/                        # Test Suite (73 tests)
│   │   ├── test_ai_engine.py
│   │   ├── test_circuit_breaker.py
│   │   ├── test_config.py
│   │   ├── test_database.py
│   │   ├── test_integration.py
│   │   ├── test_jupiter.py
│   │   ├── test_position_manager.py
│   │   ├── test_rate_limiter.py
│   │   └── test_rug_checker.py
│   │
│   ├── data_store/                   # Runtime data (gitignored)
│   ├── training/                     # Training data directory
│   ├── .env.example                  # Environment template
│   └── requirements.txt              # Python dependencies
│
├── dashboard/                        # Real-Time Dashboard (Vite + React + Tailwind)
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── App.jsx                   # Main app — tab layout, polling, state
│       ├── main.jsx
│       ├── index.css
│       └── components/
│           ├── Header.jsx            # Mode badge, connection status
│           ├── StatsBar.jsx          # Balance, P&L, win rate, trades
│           ├── PositionsTable.jsx    # Open positions with SL/TP
│           ├── ABLog.jsx             # AI vs Rule scorer comparison
│           ├── WeightsPanel.jsx      # Reactive weight visualization
│           └── ActivityFeed.jsx      # Live scan/skip/trade event stream
│
├── .gitignore
├── LICENSE                           # Proprietary — Faraone-Dev
└── README.md
```

---

## 🔧 Setup

### 1. Clone & Install

```bash
git clone https://github.com/Faraone-Dev/nexus-ai.git
cd nexus-ai/bot
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` — see `.env.example` for full documentation. Key settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | **Required.** AI provider |
| `HELIUS_API_KEY` | — | Premium RPC (recommended) |
| `BIRDEYE_API_KEY` | — | Token analytics |
| `JUPITER_API_KEY` | — | Swap routing |
| `AARNA_API_KEY` | — | Technical analysis (44 indicators) |
| `POSITION_SIZE_PERCENT` | `30` | % of balance per trade |
| `MAX_POSITIONS` | `3` | Concurrent positions |
| `STOP_LOSS_PERCENT` | `20` | Stop loss (R:R 1:2 with 40% TP) |
| `TAKE_PROFIT_PERCENT` | `40` | Take profit target |
| `MIN_LIQUIDITY_USD` | `15000` | Minimum liquidity filter |
| `SIMULATION_MODE` | `true` | Paper trading with real prices |

### 3. Get API Keys

| Service | Link | Free Tier |
|---------|------|-----------|
| **DeepSeek** | [platform.deepseek.com](https://platform.deepseek.com) | Yes |
| **Helius** | [helius.dev](https://helius.dev) | Yes |
| **Birdeye** | [birdeye.so/developers](https://birdeye.so/developers) | Yes |
| **Jupiter** | [portal.jup.ag](https://portal.jup.ag) | 600 req/min |
| **Smithery** | [smithery.ai](https://smithery.ai) | Yes |
| **Telegram** | [t.me/BotFather](https://t.me/BotFather) | Free |

### 4. Run

```bash
# Paper trading (simulation mode — recommended first)
python main.py

# Live trading (edit .env: SIMULATION_MODE=false, DRY_RUN=false)
python main.py
```

---

## 🧠 Multi-Agent AI System

4 specialized DeepSeek agents work in sequence:

### Agent #1: Token Analyzer
```
Input:  Contract address, on-chain data, TA signals
Output: Security score 0-100, red flags list
Focus:  "Is this token safe?"
```

### Agent #2: Sentiment Analyzer
```
Input:  Volume trend, holder growth, social mentions
Output: Hype score 0-100, trending direction
Focus:  "Is there momentum?"
```

### Agent #3: Risk Assessor
```
Input:  Holder distribution, LP status, dev wallet activity
Output: Rug probability %, risk level (LOW/MED/HIGH)
Focus:  "What can go wrong?"
```

### Agent #4: Master Decision
```
Input:  Results from Agent 1-3 + Aarna TA (44 indicators)
Output: BUY/SELL/WAIT, entry price, SL, TP, confidence %
Focus:  "Should we trade?"
```

**Decision Thresholds:**
- ✅ Score ≥ 65 + Confidence ≥ 70% → Execute trade
- ⚠️ Score 50-65 → Alert only (no auto-trade)
- ❌ Score < 50 → Skip

---

## 📡 Aarna MCP Integration

Technical analysis powered by [Aarna ATARS](https://smithery.ai/servers/atars-MCP/aarnaai) via Smithery Connect:

- **44 indicators** per token (RSI, MACD, Bollinger Bands, EMA cross, ADX, Stochastic, etc.)
- **Composite signal** — BULLISH / BEARISH / NEUTRAL with bullish/bearish breakdown counts
- **Transport** — JSON-RPC over HTTP via Smithery Connect API
- **Integration** — Feeds directly into Master Decision agent for TA-aware trade sizing

---

## 📊 Validation Checks

Before every trade, NEXUS runs:

| Check | Pass Criteria | Fail Action |
|-------|---------------|-------------|
| **Mint Authority** | Revoked | ❌ Block |
| **Freeze Authority** | Revoked | ❌ Block |
| **Liquidity** | > $15k | ❌ Block |
| **LP Locked** | Yes or burned | ⚠️ Warning |
| **Top Holder** | < 25% supply | ⚠️ Warning |
| **Top 10 Holders** | < 55% supply | ⚠️ Warning |
| **Contract Age** | > 30 min | ⚠️ Warning |
| **Holders Count** | ≥ 50 | ❌ Block |

---

## 📈 Learning System

```
  Trade Executed
       │
       ▼
  Wait for outcome (TP / SL / manual close)
       │
       ▼
  ReactiveAI updates per-signal weights:
  • Which data sources predicted correctly?
  • Increase weight for winning signals
  • Decrease weight for losing signals
       │
       ▼
  Every 24h — LearningEngine (DeepSeek):
  • AI post-mortem: "Why did trades win/lose?"
  • Auto-adjust thresholds, SL/TP, sizing
  • Insights saved to database
       │
       ▼
  Next scan cycle uses updated weights
```

---

## 🛡️ Infrastructure

| Module | Purpose |
|--------|---------|
| **Rate Limiter** | Token bucket per API, prevents 429s |
| **Circuit Breaker** | Halts calls to failing services, auto-recovery |
| **Resilient Client** | Retry with exponential backoff, fallback chains |
| **Health Monitor** | Tracks service health across all data providers |
| **Security Scanner** | Token vulnerability detection |

---

## � Real-Time Dashboard

Vite + React + Tailwind CSS dashboard with live bot telemetry.

```bash
cd dashboard
npm install
npm run dev          # → http://localhost:5173
```

The bot embeds an API server on `:8080` that the dashboard polls every 5 seconds.

| Tab | What It Shows |
|-----|---------------|
| **Stats Bar** | Balance, P&L, win rate, open positions, tokens analyzed |
| **Positions** | Open trades with entry/current price, P&L%, age, SL/TP |
| **A/B Test** | AI vs rule-based scorer — agreement rate, per-decision log |
| **Weights** | Reactive AI signal weights + learning stats |
| **Activity** | Live event stream — scans, rug check skips, trades |

**API Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `GET /api/stats` | Balance, P&L, trade counts, config |
| `GET /api/positions` | Open positions with computed P&L |
| `GET /api/ab-log` | AI vs rule scorer comparison log |
| `GET /api/weights` | Current reactive signal weights |
| `GET /api/activity` | Scan/skip/trade event stream |

---

## 🧪 Tests

73 tests covering AI engine, infrastructure, execution, and integration:

```bash
cd bot
python -m pytest tests/ -v --tb=short
```

| Suite | Coverage |
|-------|----------|
| `test_ai_engine` | DeepSeek client, multi-agent flow, fallback |
| `test_circuit_breaker` | Open/close states, health monitoring |
| `test_rate_limiter` | Token bucket, per-service limits |
| `test_database` | SQLite WAL, trade/scan persistence |
| `test_jupiter` | Swap routing, quote parsing |
| `test_position_manager` | SL/TP triggers, multi-position state |
| `test_rug_checker` | RugCheck scoring, threshold filtering |
| `test_config` | Env loading, defaults, validation |
| `test_integration` | End-to-end pipeline, component wiring |

---

## �🚀 Roadmap

### Phase 1: Core Bot ✅
- [x] Data aggregation (Jupiter, Birdeye, DexScreener, Helius, PumpFun)
- [x] DeepSeek AI integration (4 specialized agents)
- [x] Token validation (rug check, contract analysis)
- [x] Telegram alerts

### Phase 2: Multi-Agent AI ✅
- [x] 4 specialized agents with consensus decision
- [x] Confidence scoring + position sizing
- [x] Aarna MCP integration (44 TA indicators)

### Phase 3: Validation & Security ✅
- [x] Multi-source rug detection
- [x] Contract analyzer + security scanner
- [x] Whale wallet tracking

### Phase 4: Learning System ✅
- [x] SQLite trade database
- [x] ReactiveAI weight tuning
- [x] AI post-mortem analysis (24h cycle)

### Phase 5: Infrastructure ✅
- [x] Rate limiter, circuit breaker, resilient client
- [x] Paper trading simulator with real mainnet prices
- [x] Backtesting engine

### Phase 6: Dashboard & Testing ✅
- [x] Real-time React dashboard (Vite + Tailwind)
- [x] REST API server embedded in bot (5 endpoints)
- [x] A/B testing framework (AI vs rule-based scorer)
- [x] Activity logging and telemetry pipeline
- [x] Test suite — 73 tests, all green

### Phase 7: Production 🔨
- [ ] Extended paper trading validation
- [ ] Small capital live test
- [ ] Full deployment

---

## 💰 Business Model

### Subscription Tiers

| Tier | Price | Features |
|------|-------|----------|
| **Free** | 0€ | 3 alerts/day, no auto-trade |
| **Pro** | 29€/mo | Unlimited alerts, auto-trade |
| **Whale** | 99€/mo | Priority signals, VIP group, custom settings |

### Token Gated Access

Hold **$NEXUS** for access:

| Tier | $NEXUS Required | Access |
|------|-----------------|--------|
| Free | 0 | Basic alerts (15min delay) |
| Bronze | 10,000 | Real-time alerts |
| Silver | 50,000 | + Auto-trade |
| Gold | 200,000 | + Unlimited pairs |
| Diamond | 1,000,000 | + API access + VIP |

---

## ⚠️ Disclaimer

- Trading crypto is **HIGH RISK**
- Past performance ≠ future results
- AI can and will make mistakes
- Never trade more than you can afford to lose
- This is **NOT** financial advice — DYOR

---

## 📞 Contact

- **GitHub:** [Faraone-Dev](https://github.com/Faraone-Dev)

---

**Built with 🧠 by Faraone-Dev**
