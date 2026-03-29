"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Telegram Bot                              ║
║                        Alerts and command interface                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import httpx
from loguru import logger
from typing import Optional
from config import config


class TelegramBot:
    """
    Telegram notification and command handler
    
    Features:
    - Trading signals
    - Position updates
    - Error alerts
    - Daily summaries
    """
    
    def __init__(self):
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
        if self.enabled:
            logger.info("📱 Telegram notifications enabled")
        else:
            logger.warning("📱 Telegram not configured")
    
    async def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message
        
        Args:
            message: Message text (HTML formatting)
            parse_mode: "HTML" or "Markdown"
            
        Returns:
            Success status
        """
        if not self.enabled:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    return True
                else:
                    logger.error(f"Telegram error: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False
    
    async def send_startup(self) -> bool:
        """Send bot startup notification"""
        
        mode = "🔴 LIVE" if not config.DRY_RUN else "🟡 DRY RUN"
        
        message = f"""
🚀 <b>NEXUS AI STARTED</b> 🚀

<b>Mode:</b> {mode}
<b>Network:</b> Solana Mainnet
<b>Max Positions:</b> {config.MAX_POSITIONS}
<b>Position Size:</b> {config.POSITION_SIZE_PERCENT}%
<b>Scan Interval:</b> {config.SCAN_INTERVAL}s

<b>Filters:</b>
• Min Liquidity: ${config.MIN_LIQUIDITY_USD:,.0f}
• Min AI Score: {config.MIN_AI_SCORE}
• Min Confidence: {config.MIN_CONFIDENCE}%

<i>🤖 AI Engine: DeepSeek Multi-Agent</i>
"""
        return await self.send(message)
    
    async def send_signal(
        self,
        symbol: str,
        decision: str,
        confidence: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        reasoning: str,
        token_score: int,
        sentiment_score: int,
        risk_score: int
    ) -> bool:
        """Send trading signal alert"""
        
        emoji = "🟢" if decision == "BUY" else "🔴" if decision == "SELL" else "⚪"
        
        message = f"""
{emoji} <b>NEXUS SIGNAL: {decision}</b> {emoji}

<b>Token:</b> ${symbol}
<b>Confidence:</b> {confidence}%

<b>Levels:</b>
• Entry: ${entry_price:.8f}
• Stop Loss: ${stop_loss:.8f}
• Take Profit: ${take_profit:.8f}

<b>AI Scores:</b>
• Token: {token_score}/100
• Sentiment: {sentiment_score}/100
• Risk: {risk_score}/100

<b>Reasoning:</b>
<i>{reasoning}</i>
"""
        return await self.send(message)
    
    async def send_trade_executed(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        sol_amount: float,
        signature: Optional[str] = None
    ) -> bool:
        """Send trade execution alert"""
        
        emoji = "📈" if side.upper() == "BUY" else "📉"
        
        message = f"""
{emoji} <b>TRADE EXECUTED</b>

<b>Token:</b> ${symbol}
<b>Side:</b> {side.upper()}
<b>Amount:</b> {amount:,.0f}
<b>Price:</b> ${price:.8f}
<b>SOL:</b> {sol_amount:.4f}
"""
        
        if signature:
            short_sig = signature[:16] + "..."
            message += f"\n<a href='https://solscan.io/tx/{signature}'>View on Solscan ({short_sig})</a>"
        
        return await self.send(message)
    
    async def send_position_update(
        self,
        symbol: str,
        pnl_percent: float,
        pnl_sol: float,
        current_price: float,
        entry_price: float
    ) -> bool:
        """Send position update"""
        
        emoji = "🟢" if pnl_percent >= 0 else "🔴"
        
        message = f"""
{emoji} <b>POSITION UPDATE: ${symbol}</b>

<b>PnL:</b> {pnl_percent:+.2f}% ({pnl_sol:+.4f} SOL)
<b>Entry:</b> ${entry_price:.8f}
<b>Current:</b> ${current_price:.8f}
"""
        return await self.send(message)
    
    async def send_stop_loss(
        self,
        symbol: str,
        pnl_percent: float,
        pnl_sol: float
    ) -> bool:
        """Send stop loss alert"""
        
        message = f"""
🛑 <b>STOP LOSS TRIGGERED</b>

<b>Token:</b> ${symbol}
<b>Loss:</b> {pnl_percent:.2f}% ({pnl_sol:.4f} SOL)

<i>Position closed automatically</i>
"""
        return await self.send(message)
    
    async def send_take_profit(
        self,
        symbol: str,
        pnl_percent: float,
        pnl_sol: float
    ) -> bool:
        """Send take profit alert"""
        
        message = f"""
🎯 <b>TAKE PROFIT HIT</b> 🎉

<b>Token:</b> ${symbol}
<b>Profit:</b> +{pnl_percent:.2f}% (+{pnl_sol:.4f} SOL)

<i>Position closed automatically</i>
"""
        return await self.send(message)
    
    async def send_error(self, error: str) -> bool:
        """Send error alert"""
        
        message = f"""
⚠️ <b>NEXUS ERROR</b>

{error}

<i>Check logs for details</i>
"""
        return await self.send(message)
    
    async def send_daily_summary(
        self,
        trades_count: int,
        total_pnl_sol: float,
        win_rate: float,
        open_positions: int
    ) -> bool:
        """Send daily performance summary"""
        
        emoji = "📈" if total_pnl_sol >= 0 else "📉"
        
        message = f"""
📊 <b>NEXUS DAILY SUMMARY</b>

<b>Trades Today:</b> {trades_count}
<b>Total PnL:</b> {emoji} {total_pnl_sol:+.4f} SOL
<b>Win Rate:</b> {win_rate:.1f}%
<b>Open Positions:</b> {open_positions}/{config.MAX_POSITIONS}
"""
        return await self.send(message)
    
    async def send_shutdown(self) -> bool:
        """Send shutdown notification"""
        
        message = """
⏹️ <b>NEXUS AI STOPPED</b>

Bot has been shut down gracefully.
"""
        return await self.send(message)


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        bot = TelegramBot()
        
        if bot.enabled:
            await bot.send_startup()
            print("Startup message sent!")
        else:
            print("Telegram not configured - set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    
    asyncio.run(test())
