"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Alert Manager                             ║
║                      Centralized alert handling                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from loguru import logger
from typing import Optional
from .bot import TelegramBot
from ai.agents import TradingDecision, Decision


class AlertManager:
    """
    Centralized alert manager
    
    Handles all notifications:
    - Trading signals
    - Trade executions
    - Position updates
    - Errors
    """
    
    def __init__(self):
        self.telegram = TelegramBot()
        logger.info("Alert Manager initialized")
    
    async def signal(self, symbol: str, decision: TradingDecision) -> bool:
        """
        Send trading signal alert
        
        Args:
            symbol: Token symbol
            decision: Trading decision from AI
            
        Returns:
            Success status
        """
        if decision.decision == Decision.SKIP:
            return True  # Don't alert for skips
        
        return await self.telegram.send_signal(
            symbol=symbol,
            decision=decision.decision.value,
            confidence=decision.confidence,
            entry_price=decision.entry_price or 0,
            stop_loss=decision.stop_loss or 0,
            take_profit=decision.take_profit or 0,
            reasoning=decision.reasoning,
            token_score=decision.token_score,
            sentiment_score=decision.sentiment_score,
            risk_score=decision.risk_score
        )
    
    async def trade_executed(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        sol_amount: float,
        signature: Optional[str] = None
    ) -> bool:
        """Send trade execution alert"""
        
        return await self.telegram.send_trade_executed(
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            sol_amount=sol_amount,
            signature=signature
        )
    
    async def position_update(
        self,
        symbol: str,
        pnl_percent: float,
        pnl_sol: float,
        current_price: float,
        entry_price: float
    ) -> bool:
        """Send position update (only for significant changes)"""
        
        # Only alert for >10% moves
        if abs(pnl_percent) < 10:
            return True
        
        return await self.telegram.send_position_update(
            symbol=symbol,
            pnl_percent=pnl_percent,
            pnl_sol=pnl_sol,
            current_price=current_price,
            entry_price=entry_price
        )
    
    async def stop_loss(self, symbol: str, pnl_percent: float, pnl_sol: float) -> bool:
        """Send stop loss alert"""
        return await self.telegram.send_stop_loss(symbol, pnl_percent, pnl_sol)
    
    async def take_profit(self, symbol: str, pnl_percent: float, pnl_sol: float) -> bool:
        """Send take profit alert"""
        return await self.telegram.send_take_profit(symbol, pnl_percent, pnl_sol)
    
    async def error(self, error: str) -> bool:
        """Send error alert"""
        return await self.telegram.send_error(error)
    
    async def startup(self) -> bool:
        """Send startup alert"""
        return await self.telegram.send_startup()
    
    async def shutdown(self) -> bool:
        """Send shutdown alert"""
        return await self.telegram.send_shutdown()
    
    async def daily_summary(
        self,
        trades_count: int,
        total_pnl_sol: float,
        win_rate: float,
        open_positions: int
    ) -> bool:
        """Send daily summary"""
        return await self.telegram.send_daily_summary(
            trades_count, total_pnl_sol, win_rate, open_positions
        )
