# NEXUS AI - Smart Contracts

## Contracts

### NexusToken.sol
ERC-20 token con:
- 1 Billion supply
- 2% buy tax / 3% sell tax
- Anti-whale (max 2% wallet, 1% TX)
- Anti-bot (blacklist primi 3 blocchi)
- Sell cooldown (1 ora)
- Burn on sell
- Tier system integrato

### NexusStaking.sol
Staking con:
- 10% APY base
- Compound rewards
- Early withdraw penalty (10% se < 7 giorni)
- Tier basato su stake amount

## Quick Start

```bash
# Install
npm install

# Compile
npm run compile

# Deploy (scegli network)
npm run deploy:base      # Base
npm run deploy:bsc       # BSC
npm run deploy:arbitrum  # Arbitrum
npm run deploy:polygon   # Polygon
npm run deploy:avalanche # Avalanche

# Deploy TUTTI
npm run deploy:all
```

## Setup Pre-Deploy

1. Copia `.env.example` in `.env`
2. Inserisci la tua private key
3. Inserisci i wallet addresses
4. (Opzionale) API keys per verification

```bash
cp .env.example .env
notepad .env
```

## Post-Deploy Checklist

1. **Verifica contratti** su block explorer
2. **Add liquidity** su DEX (Uniswap/Pancake/etc)
3. **Set AMM pair**: `token.setAMM(pairAddress, true)`
4. **Enable trading**: `token.enableTrading()`
5. **Lock LP tokens** (importante per trust!)
6. **Deposit staking rewards**: transfer tokens to staking contract

## DEX per Chain

| Chain | DEX | Router |
|-------|-----|--------|
| Base | Uniswap V3 | 0x2626664c2603336E57B271c5C0b26F421741e481 |
| BSC | PancakeSwap | 0x10ED43C718714eb63d5aA57B78B54704E256024E |
| Arbitrum | Uniswap V3 | 0xE592427A0AEce92De3Edee1F18E0157C05861564 |
| Polygon | QuickSwap | 0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff |
| Avalanche | TraderJoe | 0x60aE616a2155Ee3d9A68541Ba4544862310933d4 |

## Funzioni Admin

```solidity
// Abilita trading (dopo add liquidity!)
token.enableTrading()

// Imposta pair DEX
token.setAMM(pairAddress, true)

// Rimuovi limiti (opzionale, post-launch)
token.removeLimits()

// Cambia tax
token.setTaxes(newBuyTax, newSellTax)

// Blacklist bot
token.setBlacklist(botAddress, true)

// Escludi da fees (per partner)
token.setExcludedFromFees(partnerAddress, true)
```

## Sicurezza

- ✅ OpenZeppelin contracts
- ✅ ReentrancyGuard
- ✅ Ownable con transfer
- ✅ Max tax capped (10%)
- ✅ Min limits capped (1% wallet)
- ⚠️ NON AUDITATO - usa a tuo rischio
