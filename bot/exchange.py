"""
NEXUS AI Trading Bot - Exchange Module
=======================================
Binance Futures integration via CCXT
"""

import ccxt
from loguru import logger
from config import config
from typing import Optional, Dict, List


class Exchange:
    """Binance Futures exchange wrapper"""
    
    def __init__(self):
        # Initialize exchange
        exchange_config = {
            'apiKey': config.BINANCE_API_KEY,
            'secret': config.BINANCE_SECRET_KEY,
            'sandbox': config.BINANCE_TESTNET,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True
            }
        }
        
        self.exchange = ccxt.binance(exchange_config)
        self.symbol = config.TRADING_SYMBOL
        
        # Set leverage
        self._set_leverage()
        
        logger.info(f"Exchange initialized: Binance {'TESTNET' if config.BINANCE_TESTNET else 'LIVE'}")
    
    def _set_leverage(self):
        """Set leverage for trading symbol"""
        try:
            self.exchange.set_leverage(config.TRADING_LEVERAGE, self.symbol)
            logger.info(f"Leverage set to {config.TRADING_LEVERAGE}x for {self.symbol}")
        except Exception as e:
            logger.warning(f"Could not set leverage: {e}")
    
    # ============ MARKET DATA ============
    
    def get_ticker(self) -> dict:
        """Get current ticker data"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return {
                'price': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'high_24h': ticker['high'],
                'low_24h': ticker['low'],
                'volume_24h': ticker['quoteVolume'],
                'change_24h': ticker['percentage']
            }
        except Exception as e:
            logger.error(f"Error fetching ticker: {e}")
            return {}
    
    def get_orderbook(self, limit: int = 20) -> dict:
        """Get orderbook"""
        try:
            orderbook = self.exchange.fetch_order_book(self.symbol, limit)
            return {
                'bids': orderbook['bids'],
                'asks': orderbook['asks'],
                'spread': orderbook['asks'][0][0] - orderbook['bids'][0][0] if orderbook['asks'] and orderbook['bids'] else 0
            }
        except Exception as e:
            logger.error(f"Error fetching orderbook: {e}")
            return {}
    
    def get_ohlcv(self, timeframe: str = '1h', limit: int = 100) -> list:
        """Get OHLCV candles"""
        try:
            return self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=limit)
        except Exception as e:
            logger.error(f"Error fetching OHLCV: {e}")
            return []
    
    def get_funding_rate(self) -> Optional[float]:
        """Get current funding rate"""
        try:
            funding = self.exchange.fetch_funding_rate(self.symbol)
            return funding['fundingRate'] * 100  # Convert to percentage
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")
            return None
    
    # ============ ACCOUNT ============
    
    def get_balance(self) -> dict:
        """Get account balance"""
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {})
            return {
                'total': usdt.get('total', 0),
                'free': usdt.get('free', 0),
                'used': usdt.get('used', 0)
            }
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return {'total': 0, 'free': 0, 'used': 0}
    
    def get_positions(self) -> List[dict]:
        """Get open positions"""
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            open_positions = []
            
            for pos in positions:
                if float(pos['contracts']) > 0:
                    open_positions.append({
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': pos['contracts'],
                        'entry_price': pos['entryPrice'],
                        'mark_price': pos['markPrice'],
                        'pnl': pos['unrealizedPnl'],
                        'pnl_percent': pos['percentage'],
                        'liquidation_price': pos['liquidationPrice']
                    })
            
            return open_positions
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    # ============ TRADING ============
    
    def market_order(self, side: str, amount: float) -> Optional[dict]:
        """
        Place market order
        
        Args:
            side: 'buy' or 'sell'
            amount: Size in contracts/coins
        """
        if config.DRY_RUN:
            logger.info(f"[DRY RUN] Market {side.upper()} {amount} {self.symbol}")
            return {'id': 'dry_run', 'status': 'simulated'}
        
        try:
            order = self.exchange.create_market_order(
                symbol=self.symbol,
                side=side,
                amount=amount
            )
            logger.info(f"Market order executed: {side.upper()} {amount} @ {order.get('average', 'N/A')}")
            return order
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None
    
    def limit_order(self, side: str, amount: float, price: float) -> Optional[dict]:
        """Place limit order"""
        if config.DRY_RUN:
            logger.info(f"[DRY RUN] Limit {side.upper()} {amount} {self.symbol} @ {price}")
            return {'id': 'dry_run', 'status': 'simulated'}
        
        try:
            order = self.exchange.create_limit_order(
                symbol=self.symbol,
                side=side,
                amount=amount,
                price=price
            )
            logger.info(f"Limit order placed: {side.upper()} {amount} @ {price}")
            return order
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None
    
    def set_stop_loss(self, side: str, amount: float, stop_price: float) -> Optional[dict]:
        """Set stop loss order"""
        if config.DRY_RUN:
            logger.info(f"[DRY RUN] Stop loss {side.upper()} {amount} @ {stop_price}")
            return {'id': 'dry_run', 'status': 'simulated'}
        
        try:
            # Stop loss is opposite side of position
            sl_side = 'sell' if side == 'buy' else 'buy'
            
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='stop_market',
                side=sl_side,
                amount=amount,
                params={
                    'stopPrice': stop_price,
                    'reduceOnly': True
                }
            )
            logger.info(f"Stop loss set: {sl_side.upper()} {amount} @ {stop_price}")
            return order
        except Exception as e:
            logger.error(f"Error setting stop loss: {e}")
            return None
    
    def set_take_profit(self, side: str, amount: float, tp_price: float) -> Optional[dict]:
        """Set take profit order"""
        if config.DRY_RUN:
            logger.info(f"[DRY RUN] Take profit {side.upper()} {amount} @ {tp_price}")
            return {'id': 'dry_run', 'status': 'simulated'}
        
        try:
            # Take profit is opposite side of position
            tp_side = 'sell' if side == 'buy' else 'buy'
            
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='take_profit_market',
                side=tp_side,
                amount=amount,
                params={
                    'stopPrice': tp_price,
                    'reduceOnly': True
                }
            )
            logger.info(f"Take profit set: {tp_side.upper()} {amount} @ {tp_price}")
            return order
        except Exception as e:
            logger.error(f"Error setting take profit: {e}")
            return None
    
    def close_position(self, position: dict) -> Optional[dict]:
        """Close an open position"""
        side = 'sell' if position['side'] == 'long' else 'buy'
        return self.market_order(side, position['size'])
    
    def close_all_positions(self) -> List[dict]:
        """Close all open positions"""
        positions = self.get_positions()
        results = []
        
        for pos in positions:
            result = self.close_position(pos)
            if result:
                results.append(result)
        
        return results
    
    def cancel_all_orders(self) -> bool:
        """Cancel all open orders"""
        if config.DRY_RUN:
            logger.info("[DRY RUN] Cancel all orders")
            return True
        
        try:
            self.exchange.cancel_all_orders(self.symbol)
            logger.info("All orders cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            return False
    
    # ============ UTILITY ============
    
    def calculate_position_size(self, entry_price: float) -> float:
        """Calculate position size based on config"""
        balance = self.get_balance()
        available = balance['free']
        
        # Position size as percentage of balance
        position_value = available * (config.POSITION_SIZE_PERCENT / 100)
        
        # With leverage
        position_value_leveraged = position_value * config.TRADING_LEVERAGE
        
        # Convert to contracts
        contracts = position_value_leveraged / entry_price
        
        # Round to exchange precision
        contracts = round(contracts, 3)
        
        logger.debug(f"Position size: {contracts} contracts (${position_value_leveraged:.2f})")
        
        return contracts


# Test if run directly
if __name__ == "__main__":
    exchange = Exchange()
    
    print("\n=== TICKER ===")
    print(exchange.get_ticker())
    
    print("\n=== BALANCE ===")
    print(exchange.get_balance())
    
    print("\n=== POSITIONS ===")
    print(exchange.get_positions())
    
    print("\n=== FUNDING ===")
    print(f"Funding Rate: {exchange.get_funding_rate()}%")
