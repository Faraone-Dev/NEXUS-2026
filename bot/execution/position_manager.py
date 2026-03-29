"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        NEXUS AI - Position Manager                            ║
║                    Track and manage open positions                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger
from typing import Optional
from config import config


@dataclass
class Position:
    """An open trading position"""
    id: str
    token_mint: str
    token_symbol: str
    entry_price: float
    current_price: float
    amount: float
    sol_invested: float
    stop_loss: float
    take_profit: float
    entry_time: str
    
    @property
    def pnl_percent(self) -> float:
        """Calculate PnL percentage"""
        if self.entry_price == 0:
            return 0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100
    
    @property
    def pnl_sol(self) -> float:
        """Calculate PnL in SOL"""
        return self.sol_invested * (self.pnl_percent / 100)
    
    @property
    def should_stop_loss(self) -> bool:
        """Check if stop loss triggered"""
        return self.pnl_percent <= -config.STOP_LOSS_PERCENT
    
    @property
    def should_take_profit(self) -> bool:
        """Check if take profit triggered"""
        return self.pnl_percent >= config.TAKE_PROFIT_PERCENT


class PositionManager:
    """
    Manage trading positions
    
    Features:
    - Track open positions
    - Calculate PnL
    - Stop loss / Take profit checks
    - Persist to disk
    """
    
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent.parent / "data_store"
        self.data_dir.mkdir(exist_ok=True)
        self.positions_file = self.data_dir / "positions.json"
        
        self.positions: dict[str, Position] = {}
        self._load()
        
        logger.info(f"Position Manager initialized ({len(self.positions)} positions)")
    
    def _load(self):
        """Load positions from disk"""
        if self.positions_file.exists():
            try:
                with open(self.positions_file, 'r') as f:
                    data = json.load(f)
                    for pos_id, pos_data in data.items():
                        self.positions[pos_id] = Position(**pos_data)
            except Exception as e:
                logger.error(f"Failed to load positions: {e}")
    
    def _save(self):
        """Save positions to disk"""
        try:
            data = {pos_id: asdict(pos) for pos_id, pos in self.positions.items()}
            with open(self.positions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")
    
    def open_position(
        self,
        token_mint: str,
        token_symbol: str,
        entry_price: float,
        amount: float,
        sol_invested: float
    ) -> Position:
        """
        Open a new position
        
        Args:
            token_mint: Token mint address
            token_symbol: Token symbol
            entry_price: Entry price
            amount: Token amount bought
            sol_invested: SOL spent
            
        Returns:
            Position
        """
        pos_id = f"{token_mint[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        position = Position(
            id=pos_id,
            token_mint=token_mint,
            token_symbol=token_symbol,
            entry_price=entry_price,
            current_price=entry_price,
            amount=amount,
            sol_invested=sol_invested,
            stop_loss=entry_price * (1 - config.STOP_LOSS_PERCENT / 100),
            take_profit=entry_price * (1 + config.TAKE_PROFIT_PERCENT / 100),
            entry_time=datetime.now().isoformat()
        )
        
        self.positions[pos_id] = position
        self._save()
        
        logger.info(f"📈 Position opened: {token_symbol}")
        logger.info(f"   Entry: ${entry_price:.8f}")
        logger.info(f"   Amount: {amount:,.0f}")
        logger.info(f"   Invested: {sol_invested:.4f} SOL")
        logger.info(f"   SL: ${position.stop_loss:.8f} (-{config.STOP_LOSS_PERCENT}%)")
        logger.info(f"   TP: ${position.take_profit:.8f} (+{config.TAKE_PROFIT_PERCENT}%)")
        
        return position
    
    def update_price(self, pos_id: str, current_price: float):
        """Update position's current price"""
        if pos_id in self.positions:
            self.positions[pos_id].current_price = current_price
            self._save()
    
    def update_all_prices(self, prices: dict[str, float]):
        """
        Update all positions with new prices
        
        Args:
            prices: Dict of token_mint -> current_price
        """
        for pos in self.positions.values():
            if pos.token_mint in prices:
                pos.current_price = prices[pos.token_mint]
        self._save()
    
    def close_position(self, pos_id: str) -> Optional[Position]:
        """
        Close a position
        
        Args:
            pos_id: Position ID
            
        Returns:
            Closed Position or None
        """
        if pos_id not in self.positions:
            return None
        
        position = self.positions.pop(pos_id)
        self._save()
        
        logger.info(f"📉 Position closed: {position.token_symbol}")
        logger.info(f"   PnL: {position.pnl_percent:+.2f}% ({position.pnl_sol:+.4f} SOL)")
        
        return position
    
    def get_position(self, pos_id: str) -> Optional[Position]:
        """Get position by ID"""
        return self.positions.get(pos_id)
    
    def get_position_by_token(self, token_mint: str) -> Optional[Position]:
        """Get position by token mint"""
        for pos in self.positions.values():
            if pos.token_mint == token_mint:
                return pos
        return None
    
    def get_all_positions(self) -> list[Position]:
        """Get all open positions"""
        return list(self.positions.values())
    
    def check_triggers(self) -> tuple[list[Position], list[Position]]:
        """
        Check all positions for SL/TP triggers
        
        Returns:
            (stop_loss_positions, take_profit_positions)
        """
        sl_triggered = []
        tp_triggered = []
        
        for pos in self.positions.values():
            if pos.should_stop_loss:
                sl_triggered.append(pos)
                logger.warning(f"🛑 STOP LOSS triggered: {pos.token_symbol} ({pos.pnl_percent:.2f}%)")
            elif pos.should_take_profit:
                tp_triggered.append(pos)
                logger.info(f"🎯 TAKE PROFIT triggered: {pos.token_symbol} ({pos.pnl_percent:.2f}%)")
        
        return sl_triggered, tp_triggered
    
    def get_total_pnl(self) -> float:
        """Get total PnL in SOL"""
        return sum(pos.pnl_sol for pos in self.positions.values())
    
    def get_position_count(self) -> int:
        """Get number of open positions"""
        return len(self.positions)
    
    def can_open_position(self) -> bool:
        """Check if we can open a new position"""
        return self.get_position_count() < config.MAX_POSITIONS
    
    def print_summary(self):
        """Print positions summary"""
        print("\n" + "═" * 60)
        print("                    OPEN POSITIONS")
        print("═" * 60)
        
        if not self.positions:
            print("  No open positions")
        else:
            for pos in self.positions.values():
                emoji = "🟢" if pos.pnl_percent >= 0 else "🔴"
                print(f"\n  {emoji} {pos.token_symbol}")
                print(f"     Entry: ${pos.entry_price:.8f}")
                print(f"     Current: ${pos.current_price:.8f}")
                print(f"     PnL: {pos.pnl_percent:+.2f}% ({pos.pnl_sol:+.4f} SOL)")
        
        print("\n" + "─" * 60)
        print(f"  Total Positions: {self.get_position_count()}/{config.MAX_POSITIONS}")
        print(f"  Total PnL: {self.get_total_pnl():+.4f} SOL")
        print("═" * 60 + "\n")


# Test
if __name__ == "__main__":
    manager = PositionManager()
    
    # Test opening a position
    pos = manager.open_position(
        token_mint="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        token_symbol="BONK",
        entry_price=0.00001234,
        amount=1_000_000,
        sol_invested=0.1
    )
    
    # Simulate price change
    manager.update_price(pos.id, 0.00001500)
    
    # Print summary
    manager.print_summary()
    
    # Check triggers
    sl, tp = manager.check_triggers()
    print(f"SL Triggered: {len(sl)}")
    print(f"TP Triggered: {len(tp)}")
    
    # Cleanup
    manager.close_position(pos.id)
