"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  NEXUS-2026 - TRADE SIMULATOR                                                  ║
║  Paper trading con dati REALI - Zero rischio                                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Usa prezzi REALI da mainnet ma simula le transazioni.
L'AI impara esattamente come farebbe con soldi veri.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class SimulatedPosition:
    """Posizione simulata"""
    token_address: str
    token_symbol: str
    entry_price: float
    entry_time: datetime
    amount_sol: float
    token_amount: float
    stop_loss: float
    take_profit: float

    # Tracking
    entry_value_usd: float = 0.0
    current_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    pnl_percent: float = 0.0
    pnl_sol: float = 0.0
    pnl_usd: float = 0.0
    value_returned_sol: float = 0.0
    value_returned_usd: float = 0.0
    
    # Status
    is_open: bool = True
    exit_price: float = 0.0
    exit_time: Optional[datetime] = None
    exit_reason: str = ""
    
    def update_price(self, new_price: float):
        """Aggiorna prezzo e calcola PnL"""
        self.current_price = new_price
        self.highest_price = max(self.highest_price, new_price)
        self.lowest_price = min(self.lowest_price, new_price) if self.lowest_price > 0 else new_price
        self.pnl_percent = ((new_price - self.entry_price) / self.entry_price) * 100
    
    def should_stop_loss(self) -> bool:
        """Verifica se ha colpito SL"""
        # Usa piccolo margine per evitare problemi di precisione float
        return self.pnl_percent <= -(self.stop_loss - 0.05)
    
    def should_take_profit(self) -> bool:
        """Verifica se ha colpito TP"""
        # Usa piccolo margine per evitare problemi di precisione float
        return self.pnl_percent >= (self.take_profit - 0.05)


@dataclass
class SimulatorStats:
    """Statistiche del simulatore"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_sol: float = 0.0
    total_pnl_usd: float = 0.0
    total_pnl_percent: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    current_balance: float = 1.0  # SOL simulati
    starting_balance: float = 1.0
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def roi(self) -> float:
        return ((self.current_balance - self.starting_balance) / self.starting_balance) * 100
    
    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 2),
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl_percent": round(self.total_pnl_percent, 2),
            "total_pnl_usd": round(self.total_pnl_usd, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "current_balance_sol": round(self.current_balance, 4),
            "roi_percent": round(self.roi, 2)
        }


class TradeSimulator:
    """
    Simula trading con prezzi REALI.
    Nessuna transazione on-chain - tutto in memoria.
    """
    
    def __init__(self, starting_balance: float = 1.0, max_positions: int = 3):
        self.stats = SimulatorStats(
            current_balance=starting_balance,
            starting_balance=starting_balance
        )
        self.max_positions = max_positions
        self.positions: dict[str, SimulatedPosition] = {}
        self.closed_positions: list[SimulatedPosition] = []
        
        # Fee simulation (realistic)
        self.swap_fee_percent = 0.25  # Jupiter fee
        self.slippage_percent = 0.5   # Average slippage
        
        logger.info(f"📊 Simulator initialized with {starting_balance} SOL")
    
    def open_position(
        self,
        token_address: str,
        token_symbol: str,
        current_price: float,
        amount_sol: float,
        stop_loss: float = 15.0,
        take_profit: float = 30.0
    ) -> Optional[SimulatedPosition]:
        """
        Apre una posizione simulata.
        Applica fee e slippage realistici.
        """
        # Verifica limiti
        if len(self.positions) >= self.max_positions:
            logger.warning(f"⚠️ Max positions ({self.max_positions}) reached")
            return None
        
        if token_address in self.positions:
            logger.warning(f"⚠️ Already have position in {token_symbol}")
            return None
        
        if amount_sol > self.stats.current_balance:
            logger.warning(f"⚠️ Insufficient balance: {self.stats.current_balance} SOL")
            return None
        
        # Calcola fee e slippage
        total_fee_percent = self.swap_fee_percent + self.slippage_percent
        effective_amount = amount_sol * (1 - total_fee_percent / 100)
        
        # Simula prezzo entry con slippage (peggiore del prezzo visualizzato)
        slippage_multiplier = 1 + (random.uniform(0.1, self.slippage_percent) / 100)
        entry_price = current_price * slippage_multiplier
        
        # Calcola token amount (Solana gas ~0.000005 SOL, negligible)
        token_amount = effective_amount / entry_price
        
        # Crea posizione
        position = SimulatedPosition(
            token_address=token_address,
            token_symbol=token_symbol,
            entry_price=entry_price,
            entry_time=datetime.now(),
            amount_sol=amount_sol,
            token_amount=token_amount,
            stop_loss=stop_loss,
            take_profit=take_profit,
            entry_value_usd=token_amount * entry_price,
            current_price=entry_price,
            highest_price=entry_price,
            lowest_price=entry_price
        )
        
        # Aggiorna balance
        self.stats.current_balance -= amount_sol
        self.positions[token_address] = position
        
        logger.info(f"📈 SIMULATED BUY: {token_symbol}")
        logger.info(f"   Entry: ${entry_price:.8f}")
        logger.info(f"   Amount: {amount_sol} SOL → {token_amount:.2f} tokens")
        logger.info(f"   SL: -{stop_loss}% | TP: +{take_profit}%")
        
        return position
    
    def close_position(
        self,
        token_address: str,
        current_price: float,
        reason: str = "manual"
    ) -> Optional[SimulatedPosition]:
        """
        Chiude una posizione simulata.
        Applica fee e slippage sull'exit.
        """
        if token_address not in self.positions:
            return None
        
        position = self.positions[token_address]
        
        # Simula slippage exit (peggiore del prezzo visualizzato)
        slippage_multiplier = 1 - (random.uniform(0.1, self.slippage_percent) / 100)
        exit_price = current_price * slippage_multiplier
        
        # Calcola PnL finale
        position.update_price(exit_price)
        position.exit_price = exit_price
        position.exit_time = datetime.now()
        position.exit_reason = reason
        position.is_open = False
        
        # Calcola quanto ritorna (meno fee)
        value_before_fee_usd = position.token_amount * exit_price
        fee_usd = value_before_fee_usd * (self.swap_fee_percent / 100)
        value_returned_usd = value_before_fee_usd - fee_usd

        entry_value_usd = position.entry_value_usd or (position.token_amount * position.entry_price)
        sol_per_usd_at_entry = position.amount_sol / entry_value_usd if entry_value_usd else 0
        value_returned_sol = value_returned_usd * sol_per_usd_at_entry if sol_per_usd_at_entry else position.amount_sol
        pnl_sol = value_returned_sol - position.amount_sol
        pnl_usd = value_returned_usd - entry_value_usd

        position.value_returned_sol = value_returned_sol
        position.value_returned_usd = value_returned_usd
        position.pnl_sol = pnl_sol
        position.pnl_usd = pnl_usd

        # Aggiorna stats
        self.stats.current_balance += value_returned_sol
        self.stats.total_trades += 1
        self.stats.total_pnl_sol += pnl_sol
        self.stats.total_pnl_usd += pnl_usd
        self.stats.total_pnl_percent += position.pnl_percent
        
        if pnl_sol > 0:
            self.stats.winning_trades += 1
            self.stats.largest_win = max(self.stats.largest_win, position.pnl_percent)
        else:
            self.stats.losing_trades += 1
            self.stats.largest_loss = min(self.stats.largest_loss, position.pnl_percent)
        
        # Sposta a closed
        self.closed_positions.append(position)
        del self.positions[token_address]
        
        # Log
        emoji = "✅" if pnl_sol > 0 else "❌"
        logger.info(f"{emoji} SIMULATED SELL: {position.token_symbol}")
        logger.info(f"   Exit: ${exit_price:.8f}")
        logger.info(
            f"   Value Out: {value_returned_sol:.4f} SOL | ${value_returned_usd:,.2f}"
        )
        logger.info(f"   PnL: {position.pnl_percent:+.2f}% ({pnl_sol:+.4f} SOL)")
        logger.info(f"   Reason: {reason}")
        logger.info(f"   Balance: {self.stats.current_balance:.4f} SOL")
        
        return position
    
    def update_positions(self, prices: dict[str, float]) -> list[SimulatedPosition]:
        """
        Aggiorna prezzi di tutte le posizioni.
        Ritorna lista di posizioni che hanno triggerato SL/TP.
        """
        triggered = []
        
        for token_address, position in list(self.positions.items()):
            if token_address not in prices:
                continue
            
            current_price = prices[token_address]
            position.update_price(current_price)
            
            # Check SL/TP
            if position.should_stop_loss():
                closed = self.close_position(token_address, current_price, "stop_loss")
                if closed:
                    triggered.append(closed)
            elif position.should_take_profit():
                closed = self.close_position(token_address, current_price, "take_profit")
                if closed:
                    triggered.append(closed)
        
        return triggered
    
    def get_open_positions(self) -> list[dict]:
        """Ritorna posizioni aperte come dict"""
        return [
            {
                "symbol": p.token_symbol,
                "address": p.token_address,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "pnl_percent": round(p.pnl_percent, 2),
                "amount_sol": p.amount_sol,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "entry_time": p.entry_time.isoformat()
            }
            for p in self.positions.values()
        ]
    
    def get_summary(self) -> str:
        """Ritorna summary leggibile"""
        stats = self.stats
        
        summary = f"""
╔══════════════════════════════════════════════════════════════╗
║  📊 SIMULATOR STATS                                           ║
╠══════════════════════════════════════════════════════════════╣
║  Balance: {stats.current_balance:.4f} SOL (started: {stats.starting_balance} SOL)
║  ROI: {stats.roi:+.2f}%
║
║  Trades: {stats.total_trades}
║  Win Rate: {stats.win_rate:.1f}% ({stats.winning_trades}W / {stats.losing_trades}L)
║  Total PnL: {stats.total_pnl_sol:+.4f} SOL ({stats.total_pnl_usd:+,.2f} USD)
║  
║  Largest Win:  {stats.largest_win:+.2f}%
║  Largest Loss: {stats.largest_loss:+.2f}%
║
║  Open Positions: {len(self.positions)}/{self.max_positions}
╚══════════════════════════════════════════════════════════════╝
"""
        return summary


# ═══════════════════════════════════════════════════════════════════════════════
#  INTEGRATION CON NEXUS
# ═══════════════════════════════════════════════════════════════════════════════

class NexusSimulatorBridge:
    """
    Bridge tra NEXUS e il simulatore.
    Sostituisce le chiamate reali a Jupiter con simulazioni.
    """
    
    def __init__(self, simulator: TradeSimulator, db=None):
        self.simulator = simulator
        self.db = db
    
    async def execute_buy(
        self,
        token_address: str,
        token_symbol: str,
        current_price: float,
        amount_sol: float,
        confidence: float,
        stop_loss: float,
        take_profit: float
    ) -> dict:
        """
        Esegue un buy simulato.
        Salva in DB come trade reale per learning.
        """
        position = self.simulator.open_position(
            token_address=token_address,
            token_symbol=token_symbol,
            current_price=current_price,
            amount_sol=amount_sol,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        if not position:
            return {"success": False, "error": "Could not open position"}
        
        # Salva in DB per learning
        if self.db:
            await self.db.save_trade(
                token_address=token_address,
                token_symbol=token_symbol,
                action="buy",
                amount_sol=amount_sol,
                price=position.entry_price,
                confidence=confidence,
                tx_hash=f"SIM_{token_address[:8]}_{int(datetime.now().timestamp())}",
                is_simulated=True
            )
        
        return {
            "success": True,
            "position": position,
            "entry_price": position.entry_price,
            "token_amount": position.token_amount
        }
    
    async def execute_sell(
        self,
        token_address: str,
        current_price: float,
        reason: str
    ) -> dict:
        """
        Esegue un sell simulato.
        Aggiorna trade in DB per learning.
        """
        position = self.simulator.close_position(
            token_address=token_address,
            current_price=current_price,
            reason=reason
        )
        
        if not position:
            return {"success": False, "error": "Position not found"}
        
        # Aggiorna DB per learning
        if self.db:
            await self.db.save_trade(
                token_address=token_address,
                token_symbol=position.token_symbol,
                action="sell",
                amount_sol=position.amount_sol,
                price=position.exit_price,
                confidence=0,
                tx_hash=f"SIM_SELL_{token_address[:8]}_{int(datetime.now().timestamp())}",
                pnl_percent=position.pnl_percent,
                is_simulated=True
            )
        
        return {
            "success": True,
            "position": position,
            "pnl_percent": position.pnl_percent,
            "exit_price": position.exit_price
        }
