# ◈ NEXUS AI — MASTER PLAN

## VISIONE

Token $NEXUS + AI Trading Bot = Ecosistema completo.
Chi holda $NEXUS → accesso al bot → bot performa → token sale → tutti felici.

---

## 🏗️ ARCHITETTURA COMPLETA

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           NEXUS ECOSYSTEM                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐   │
│   │   WEBSITE   │     │   $NEXUS    │     │      AI TRADING BOT     │   │
│   │   Landing   │────▶│   TOKEN     │────▶│   (Il cuore)            │   │
│   │   + App     │     │   ERC-20    │     │                         │   │
│   └─────────────┘     └─────────────┘     └─────────────────────────┘   │
│         │                   │                         │                  │
│         ▼                   ▼                         ▼                  │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐   │
│   │  Marketing  │     │   Staking   │     │   Multi-Exchange        │   │
│   │  Hype       │     │   Rewards   │     │   Binance/Bybit/OKX     │   │
│   │  Community  │     │   Revenue   │     │   Hyperliquid           │   │
│   └─────────────┘     └─────────────┘     └─────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 STRUTTURA PROGETTO

```
nexus-2026/
├── website/                    # Landing page (GIÀ FATTO ✅)
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── bot/                        # AI Trading Bot (GIÀ FATTO ✅)
│   ├── main.py                 # Entry point
│   ├── config.py               # Env variables
│   ├── ai_engine.py            # DeepSeek integration
│   ├── exchange.py             # Binance/multi-exchange
│   ├── data_fetcher.py         # Market data
│   ├── trader.py               # Trading logic
│   ├── telegram_bot.py         # Alerts
│   └── .env                    # API keys
│
├── contracts/                  # Smart Contracts (DA FARE 🔨)
│   ├── NexusToken.sol          # ERC-20 Token
│   ├── NexusStaking.sol        # Staking per rewards
│   └── NexusVault.sol          # (Opzionale) Depositi + bot trada
│
├── dashboard/                  # User Dashboard (DA FARE 🔨)
│   ├── Connetti wallet
│   ├── Vedi holdings $NEXUS
│   ├── Attiva/disattiva bot
│   └── Vedi performance
│
└── scripts/                    # Deploy & Utils
    ├── deploy.js
    └── verify.js
```

---

## 💰 TOKENOMICS $NEXUS

### Supply & Distribution

| Allocazione | % | Tokens | Lock |
|-------------|---|--------|------|
| **Public Sale** | 40% | 400,000,000 | Nessuno |
| **Liquidity Pool** | 25% | 250,000,000 | Lock 1 anno |
| **Team** | 15% | 150,000,000 | Vesting 2 anni |
| **Staking Rewards** | 10% | 100,000,000 | Release graduale |
| **Marketing** | 5% | 50,000,000 | Unlock trimestrale |
| **Reserve** | 5% | 50,000,000 | DAO controlled |
| **TOTAL** | 100% | 1,000,000,000 | - |

### Tax Structure

| Azione | Tax | Destinazione |
|--------|-----|--------------|
| Buy | 2% | 1% LP + 1% Staking |
| Sell | 3% | 1% LP + 1% Staking + 1% Burn |
| Transfer | 0% | - |

### Anti-Dump Mechanics

- Max wallet: 2% supply (20M tokens)
- Max TX: 1% supply (10M tokens)
- Sell cooldown: 1 ora tra sells
- Anti-bot: primi 3 blocchi blacklist

---

## 🤖 BOT TIERS (Chi holda di più → più features)

| Tier | $NEXUS Required | Features |
|------|-----------------|----------|
| **Free** | 0 | Solo segnali Telegram (delay 15 min) |
| **Bronze** | 10,000 | Segnali real-time + 1 pair |
| **Silver** | 50,000 | + 5 pairs + auto-trade testnet |
| **Gold** | 200,000 | + Illimitato + auto-trade live |
| **Diamond** | 1,000,000 | + API privata + priorità + support VIP |

---

## 🔄 REVENUE FLOW

```
                    ┌──────────────────┐
                    │   USER TRADES    │
                    │   $NEXUS         │
                    └────────┬─────────┘
                             │
                    2-3% Tax │
                             ▼
         ┌───────────────────┴───────────────────┐
         │                                       │
         ▼                                       ▼
┌─────────────────┐                   ┌─────────────────┐
│  LIQUIDITY POOL │                   │ STAKING REWARDS │
│  (Price floor)  │                   │ (Incentivo hold)│
└─────────────────┘                   └─────────────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │   BOT ACCESS    │
                                      │   (Utility)     │
                                      └─────────────────┘
```

---

## 🚀 ROADMAP REALE

### FASE 1: Token Launch (Settimana 1)
- [ ] Deploy $NEXUS su Base (cheap + hype)
- [ ] Verifica su Basescan
- [ ] Add liquidity su Uniswap V3
- [ ] List su DexScreener, DexTools

### FASE 2: Bot Integration (Settimana 2)
- [ ] Sistema verifica holdings on-chain
- [ ] Gate tiers (chi holda X → accesso Y)
- [ ] Telegram bot per verifica
- [ ] Dashboard connetti wallet

### FASE 3: Staking (Settimana 3)
- [ ] Deploy NexusStaking.sol
- [ ] APY basato su tier
- [ ] UI staking nel dashboard

### FASE 4: Marketing Blitz (Ongoing)
- [ ] Twitter/X shilling
- [ ] Telegram gruppo
- [ ] Influencer DeFi
- [ ] Meme + viral content
- [ ] Listings CoinGecko/CMC

---

## 🔐 SMART CONTRACTS

### NexusToken.sol (Core)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract NexusToken is ERC20, Ownable {
    
    // Anti-whale
    uint256 public maxWallet = totalSupply() * 2 / 100;      // 2%
    uint256 public maxTx = totalSupply() * 1 / 100;          // 1%
    
    // Tax
    uint256 public buyTax = 2;   // 2%
    uint256 public sellTax = 3;  // 3%
    
    // Addresses
    address public liquidityWallet;
    address public stakingWallet;
    
    // DEX
    mapping(address => bool) public isExcludedFromFees;
    mapping(address => bool) public isAMM;
    
    // Anti-bot
    uint256 public launchBlock;
    mapping(address => bool) public isBlacklisted;
    mapping(address => uint256) public lastSellTime;
    uint256 public sellCooldown = 1 hours;
    
    // ... implementazione completa sotto
}
```

---

## 💻 TECH STACK

| Component | Technology |
|-----------|------------|
| Token | Solidity + OpenZeppelin |
| Chain | Base (L2 Ethereum) |
| Bot | Python + DeepSeek + CCXT |
| Exchange | Binance Futures (+ Bybit, Hyperliquid) |
| Frontend | HTML/CSS/JS (già fatto) |
| Dashboard | React o vanilla JS |
| Wallet Connect | WalletConnect v2 |
| Hosting | Vercel / Netlify |
| DB | Supabase (user data) |

---

## ⚡ QUICK START

### 1. Deploy Token
```bash
cd contracts
npx hardhat run scripts/deploy.js --network base
npx hardhat verify --network base <CONTRACT_ADDRESS>
```

### 2. Add Liquidity
- Vai su Uniswap (Base)
- Pair $NEXUS/ETH
- Add liquidity iniziale
- Lock LP tokens (importante per trust)

### 3. Bot Già Pronto
```bash
cd bot
cp .env.example .env
# Inserisci API keys
pip install -r requirements.txt
python main.py
```

### 4. Connetti Token al Bot
- Bot legge wallet balance on-chain
- Se balance ≥ tier → accesso features
- Verifica via firma wallet

---

## 📊 ESEMPIO USE CASE

1. **Mario** compra 50,000 $NEXUS su Uniswap
2. Mario va su nexus-ai.xyz/dashboard
3. Connette wallet (MetaMask)
4. Bot verifica: "Hai 50k = Tier Silver ✅"
5. Mario attiva bot → riceve segnali + auto-trade testnet
6. Mario vuole auto-trade live → deve comprare 200k (Tier Gold)
7. Mario compra altri 150k → prezzo $NEXUS sale
8. Tutti vincono 🚀

---

## ⚠️ LEGAL DISCLAIMER

- Questo token NON è un investimento
- NON promettiamo returns
- Il bot NON garantisce profitti
- Trading = rischio
- DYOR (Do Your Own Research)
- Non siamo financial advisors

---

## 🎯 OBIETTIVI

| Metrica | Target 30 giorni | Target 90 giorni |
|---------|------------------|------------------|
| Holders | 1,000 | 10,000 |
| Market Cap | $500k | $5M |
| TVL Staking | $100k | $1M |
| Bot Users | 100 | 1,000 |
| Telegram Members | 5,000 | 50,000 |

---

## PROSSIMI STEP IMMEDIATI

1. ✅ Website (fatto)
2. ✅ Bot (fatto)
3. 🔨 **ORA: Smart Contract** → Deploy token
4. 🔨 Dashboard + wallet connect
5. 🔨 Telegram bot per verify
6. 🔨 Marketing push

---

**LET'S FUCKING GO** 🚀
