"""
NEXUS AI Trading Bot - Main Entry Point
========================================
Start the bot and run the main loop
"""

import sys
import time
import signal
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler

from config import config, Config
from trader import Trader
from telegram_bot import TelegramBot


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    level=config.LOG_LEVEL
)
logger.add(
    "logs/nexus_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG"
)


class NexusBot:
    """Main bot class"""
    
    def __init__(self):
        self.trader = None
        self.telegram = None
        self.scheduler = None
        self.running = False
        
    def validate_config(self) -> bool:
        """Validate configuration before starting"""
        
        errors = Config.validate()
        
        if errors:
            logger.error("Configuration errors:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        return True
    
    def setup(self) -> bool:
        """Initialize all components"""
        
        logger.info("="*50)
        logger.info("NEXUS AI TRADING BOT")
        logger.info("="*50)
        
        # Validate config
        if not self.validate_config():
            return False
        
        # Print config
        Config.print_config()
        
        # Initialize components
        try:
            self.trader = Trader()
            self.telegram = TelegramBot()
            
            # Setup scheduler
            self.scheduler = BlockingScheduler()
            
            # Schedule analysis job
            self.scheduler.add_job(
                self.analysis_cycle,
                'interval',
                seconds=config.ANALYSIS_INTERVAL,
                id='analysis',
                next_run_time=datetime.now()  # Run immediately
            )
            
            # Schedule daily summary
            self.scheduler.add_job(
                self.daily_summary,
                'cron',
                hour=0,
                minute=0,
                id='daily_summary'
            )
            
            logger.info("Setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False
    
    def analysis_cycle(self):
        """Main analysis and trading cycle"""
        
        try:
            logger.info("-" * 40)
            logger.info(f"Analysis cycle started at {datetime.now().strftime('%H:%M:%S')}")
            
            # Run analysis
            decision = self.trader.run_analysis()
            
            # Execute if actionable
            if decision.get('decision') != 'WAIT' and decision.get('confidence', 0) >= 70:
                self.trader.execute_decision(decision)
            
            # Check positions
            self.trader.check_positions()
            
            logger.info(f"Next analysis in {config.ANALYSIS_INTERVAL} seconds")
            
        except Exception as e:
            logger.error(f"Analysis cycle error: {e}")
            self.telegram.send_error(str(e))
    
    def daily_summary(self):
        """Send daily performance summary"""
        
        try:
            status = self.trader.get_status()
            balance = status['balance']['total']
            
            self.telegram.send_daily_summary(
                trades=self.trader.trades_today,
                pnl=self.trader.daily_pnl,
                balance=balance
            )
            
            # Reset daily counters
            self.trader.trades_today = 0
            self.trader.daily_pnl = 0.0
            
        except Exception as e:
            logger.error(f"Daily summary error: {e}")
    
    def start(self):
        """Start the bot"""
        
        if not self.setup():
            logger.error("Failed to start bot")
            sys.exit(1)
        
        # Send startup notification
        self.telegram.send_startup()
        
        self.running = True
        
        logger.info("Bot started! Press Ctrl+C to stop.")
        
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stop()
    
    def stop(self):
        """Stop the bot gracefully"""
        
        logger.info("Stopping bot...")
        
        self.running = False
        
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        
        # Notify
        if self.telegram:
            self.telegram.send("🛑 <b>NEXUS BOT STOPPED</b>")
        
        logger.info("Bot stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Shutdown signal received")
    sys.exit(0)


def main():
    """Main entry point"""
    
    # Handle signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start bot
    bot = NexusBot()
    bot.start()


if __name__ == "__main__":
    main()
