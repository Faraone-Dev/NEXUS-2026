"""
NEXUS AI Trading Bot - Telegram Notifications
==============================================
Send alerts and updates via Telegram
"""

import requests
from loguru import logger
from config import config


class TelegramBot:
    """Telegram notification handler"""
    
    def __init__(self):
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        
        if self.enabled:
            logger.info("Telegram notifications enabled")
        else:
            logger.warning("Telegram not configured - notifications disabled")
    
    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram"""
        
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False
    
    def send_signal(self, decision: str, confidence: int, reasoning: str, 
                    entry: float = None, sl: float = None, tp: float = None) -> bool:
        """Send trading signal alert"""
        
        emoji = "🟢" if decision == "LONG" else "🔴" if decision == "SHORT" else "⚪"
        
        message = f"""
{emoji} <b>NEXUS AI SIGNAL</b> {emoji}

<b>Decision:</b> {decision}
<b>Confidence:</b> {confidence}%
<b>Reasoning:</b> {reasoning}
"""
        
        if entry:
            message += f"\n<b>Entry:</b> ${entry:,.2f}"
        if sl:
            message += f"\n<b>Stop Loss:</b> ${sl:,.2f}"
        if tp:
            message += f"\n<b>Take Profit:</b> ${tp:,.2f}"
        
        message += f"\n\n⏰ <i>{config.TRADING_SYMBOL}</i>"
        
        return self.send(message)
    
    def send_trade_executed(self, side: str, amount: float, price: float, 
                            pnl: float = None) -> bool:
        """Send trade execution alert"""
        
        emoji = "📈" if side.upper() == "BUY" else "📉"
        
        message = f"""
{emoji} <b>TRADE EXECUTED</b>

<b>Side:</b> {side.upper()}
<b>Amount:</b> {amount}
<b>Price:</b> ${price:,.2f}
<b>Symbol:</b> {config.TRADING_SYMBOL}
"""
        
        if pnl is not None:
            pnl_emoji = "💰" if pnl >= 0 else "💸"
            message += f"\n{pnl_emoji} <b>PnL:</b> ${pnl:,.2f}"
        
        return self.send(message)
    
    def send_error(self, error: str) -> bool:
        """Send error alert"""
        
        message = f"""
⚠️ <b>NEXUS BOT ERROR</b>

{error}

<i>Please check the bot logs</i>
"""
        return self.send(message)
    
    def send_daily_summary(self, trades: int, pnl: float, balance: float, 
                           win_rate: float = None) -> bool:
        """Send daily performance summary"""
        
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        
        message = f"""
📊 <b>NEXUS DAILY SUMMARY</b>

<b>Trades Today:</b> {trades}
<b>Total PnL:</b> {pnl_emoji} ${pnl:,.2f}
<b>Current Balance:</b> ${balance:,.2f}
"""
        
        if win_rate is not None:
            message += f"<b>Win Rate:</b> {win_rate:.1f}%"
        
        return self.send(message)
    
    def send_startup(self) -> bool:
        """Send bot startup notification"""
        
        mode = "🔴 LIVE" if not config.DRY_RUN else "🟡 DRY RUN"
        testnet = "TESTNET" if config.BINANCE_TESTNET else "MAINNET"
        
        message = f"""
🚀 <b>NEXUS AI BOT STARTED</b>

<b>Mode:</b> {mode}
<b>Exchange:</b> Binance {testnet}
<b>Symbol:</b> {config.TRADING_SYMBOL}
<b>Leverage:</b> {config.TRADING_LEVERAGE}x
<b>Analysis Interval:</b> {config.ANALYSIS_INTERVAL}s

<i>AI Engine: DeepSeek</i>
"""
        return self.send(message)


# Test if run directly
if __name__ == "__main__":
    bot = TelegramBot()
    
    if bot.enabled:
        bot.send_startup()
        print("Startup message sent!")
    else:
        print("Telegram not configured")
