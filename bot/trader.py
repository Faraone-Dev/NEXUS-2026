"""
NEXUS AI Trading Bot - Trading Logic
=====================================
Executes trades based on AI decisions
"""

from loguru import logger
from config import config
from exchange import Exchange
from ai_engine import AIEngine
from data_fetcher import DataFetcher
from telegram_bot import TelegramBot
from typing import Optional, Dict


class Trader:
    """Main trading logic handler"""
    
    def __init__(self):
        self.exchange = Exchange()
        self.ai = AIEngine()
        self.data_fetcher = DataFetcher(self.exchange)
        self.telegram = TelegramBot()
        
        # State
        self.last_decision = None
        self.trades_today = 0
        self.daily_pnl = 0.0
        
        logger.info("Trader initialized")
    
    def run_analysis(self) -> dict:
        """Run full analysis cycle"""
        
        logger.info("Starting analysis cycle...")
        
        # 1. Fetch all market data
        market_data = self.data_fetcher.get_all_data()
        logger.debug(f"Market data: {market_data}")
        
        # 2. Get AI decision
        decision = self.ai.analyze(market_data)
        
        # 3. Store decision
        self.last_decision = decision
        
        return decision
    
    def execute_decision(self, decision: dict) -> Optional[dict]:
        """Execute a trading decision"""
        
        action = decision.get('decision', 'WAIT')
        confidence = decision.get('confidence', 0)
        
        # Check confidence threshold
        if confidence < 70:
            logger.info(f"Confidence too low ({confidence}%), skipping trade")
            return None
        
        # Check if WAIT
        if action == 'WAIT':
            logger.info("AI says WAIT, no action")
            return None
        
        # Check existing positions
        positions = self.exchange.get_positions()
        
        # Don't open if already at max positions
        if len(positions) >= config.MAX_POSITIONS:
            logger.warning(f"Max positions ({config.MAX_POSITIONS}) reached, skipping")
            return None
        
        # Check if already in same direction
        for pos in positions:
            if (action == 'LONG' and pos['side'] == 'long') or \
               (action == 'SHORT' and pos['side'] == 'short'):
                logger.info(f"Already {action}, skipping duplicate")
                return None
        
        # Get current price
        ticker = self.exchange.get_ticker()
        current_price = ticker.get('price', 0)
        
        if not current_price:
            logger.error("Could not get current price")
            return None
        
        # Calculate position size
        position_size = self.exchange.calculate_position_size(current_price)
        
        if position_size <= 0:
            logger.error("Position size is 0, check balance")
            return None
        
        # Calculate SL/TP
        if action == 'LONG':
            sl_price = decision.get('stop_loss') or current_price * (1 - config.STOP_LOSS_PERCENT / 100)
            tp_price = decision.get('take_profit') or current_price * (1 + config.TAKE_PROFIT_PERCENT / 100)
            side = 'buy'
        else:  # SHORT
            sl_price = decision.get('stop_loss') or current_price * (1 + config.STOP_LOSS_PERCENT / 100)
            tp_price = decision.get('take_profit') or current_price * (1 - config.TAKE_PROFIT_PERCENT / 100)
            side = 'sell'
        
        # Send signal to Telegram
        self.telegram.send_signal(
            decision=action,
            confidence=confidence,
            reasoning=decision.get('reasoning', ''),
            entry=current_price,
            sl=sl_price,
            tp=tp_price
        )
        
        # Execute trade
        order = self.exchange.market_order(side, position_size)
        
        if order:
            # Set SL/TP
            self.exchange.set_stop_loss(side, position_size, sl_price)
            self.exchange.set_take_profit(side, position_size, tp_price)
            
            # Notify
            self.telegram.send_trade_executed(
                side=side,
                amount=position_size,
                price=current_price
            )
            
            self.trades_today += 1
            
            logger.info(f"Trade executed: {action} {position_size} @ {current_price}")
            logger.info(f"SL: {sl_price}, TP: {tp_price}")
            
            return order
        
        return None
    
    def check_positions(self) -> None:
        """Check and log current positions"""
        
        positions = self.exchange.get_positions()
        
        if positions:
            logger.info(f"Open positions: {len(positions)}")
            for pos in positions:
                logger.info(f"  {pos['side'].upper()} {pos['size']} @ {pos['entry_price']} | PnL: ${pos['pnl']:.2f}")
        else:
            logger.info("No open positions")
    
    def close_all(self) -> None:
        """Emergency close all positions"""
        
        logger.warning("CLOSING ALL POSITIONS")
        
        self.exchange.cancel_all_orders()
        results = self.exchange.close_all_positions()
        
        if results:
            self.telegram.send("⚠️ <b>ALL POSITIONS CLOSED</b>")
            logger.info(f"Closed {len(results)} positions")
        else:
            logger.info("No positions to close")
    
    def get_status(self) -> dict:
        """Get current bot status"""
        
        balance = self.exchange.get_balance()
        positions = self.exchange.get_positions()
        
        return {
            'balance': balance,
            'positions': positions,
            'trades_today': self.trades_today,
            'daily_pnl': self.daily_pnl,
            'last_decision': self.last_decision,
            'dry_run': config.DRY_RUN
        }


# Test if run directly
if __name__ == "__main__":
    trader = Trader()
    
    # Run one analysis cycle
    decision = trader.run_analysis()
    print(f"\nDecision: {decision}")
    
    # Check positions
    trader.check_positions()
    
    # Get status
    status = trader.get_status()
    print(f"\nStatus: {status}")
