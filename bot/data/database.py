"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Database                                  ║
║                    SQLite storage for trade history & learning                ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, Set
from loguru import logger


@dataclass
class TradeRecord:
    """Complete trade record for learning"""
    id: Optional[int]
    token_mint: str
    token_symbol: str
    side: str  # BUY / SELL
    entry_price: float
    exit_price: Optional[float]
    amount: float
    sol_invested: float
    sol_returned: Optional[float]
    pnl_sol: Optional[float]
    pnl_percent: Optional[float]
    
    # AI scores at entry
    token_score: int
    sentiment_score: int
    risk_score: int
    ai_confidence: int
    
    # Token metrics at entry
    liquidity: float
    volume_24h: float
    holder_count: int
    age_hours: float
    top_10_percent: float
    
    # Outcome
    outcome: str  # WIN / LOSS / OPEN
    hold_time_hours: Optional[float]
    exit_reason: Optional[str]  # TP / SL / MANUAL
    
    # Timestamps
    entry_time: str
    exit_time: Optional[str]
    
    # Flags
    is_simulated: bool = False

    # Extra data (JSON)
    extra_data: Optional[str] = None


@dataclass
class TokenScan:
    """Record of scanned tokens (for pattern learning)"""
    id: Optional[int]
    token_mint: str
    token_symbol: str
    scan_time: str
    
    # Metrics at scan
    price: float
    liquidity: float
    volume_24h: float
    holder_count: int
    age_hours: float
    
    # AI decision
    ai_decision: str  # BUY / SKIP
    ai_confidence: int
    token_score: int
    sentiment_score: int
    risk_score: int
    
    # What happened after (filled later)
    price_1h_later: Optional[float] = None
    price_24h_later: Optional[float] = None
    was_rug: Optional[bool] = None


class Database:
    """
    SQLite database for NEXUS AI
    
    Tables:
    - trades: All executed trades with outcomes
    - scans: All token scans (for backtesting AI decisions)
    - whale_alerts: Whale transaction alerts
    - learning_stats: Aggregated learning metrics
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = Path(__file__).parent.parent / "data_store"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "nexus.db")
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._configure_connection()
        self._create_tables()
        logger.info(f"Database initialized: {db_path}")

    def _configure_connection(self):
        """Apply performance-oriented pragmas."""
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.execute("PRAGMA cache_size=-20000;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        self.conn.commit()
    
    def _create_tables(self):
        """Create all tables"""
        cursor = self.conn.cursor()
        
        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_mint TEXT NOT NULL,
                token_symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                is_simulated INTEGER DEFAULT 0,
                exit_price REAL,
                amount REAL NOT NULL,
                sol_invested REAL NOT NULL,
                sol_returned REAL,
                pnl_sol REAL,
                pnl_percent REAL,
                
                token_score INTEGER,
                sentiment_score INTEGER,
                risk_score INTEGER,
                ai_confidence INTEGER,
                
                liquidity REAL,
                volume_24h REAL,
                holder_count INTEGER,
                age_hours REAL,
                top_10_percent REAL,
                
                outcome TEXT DEFAULT 'OPEN',
                hold_time_hours REAL,
                exit_reason TEXT,
                
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                extra_data TEXT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Scans table (for learning from skipped tokens too)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_mint TEXT NOT NULL,
                token_symbol TEXT NOT NULL,
                scan_time TEXT NOT NULL,
                
                price REAL,
                liquidity REAL,
                volume_24h REAL,
                holder_count INTEGER,
                age_hours REAL,
                
                ai_decision TEXT,
                ai_confidence INTEGER,
                token_score INTEGER,
                sentiment_score INTEGER,
                risk_score INTEGER,
                
                price_1h_later REAL,
                price_24h_later REAL,
                was_rug INTEGER,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Whale alerts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whale_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_mint TEXT NOT NULL,
                token_symbol TEXT,
                whale_address TEXT NOT NULL,
                action TEXT NOT NULL,
                amount_usd REAL,
                amount_tokens REAL,
                signature TEXT,
                timestamp TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Learning stats (aggregated)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_pnl_sol REAL DEFAULT 0,
                avg_win_percent REAL,
                avg_loss_percent REAL,
                best_trade_pnl REAL,
                worst_trade_pnl REAL,
                avg_hold_time_hours REAL,
                tokens_scanned INTEGER DEFAULT 0,
                buy_rate REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_mint ON trades(token_mint)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_outcome ON trades(outcome)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_mint_outcome_created ON trades(token_mint, outcome, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_mint ON scans(token_mint)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_whale_mint ON whale_alerts(token_mint)")
        
        # Migration: add is_simulated column if not exists
        try:
            cursor.execute("ALTER TABLE trades ADD COLUMN is_simulated INTEGER DEFAULT 0")
            logger.info("Migration: Added is_simulated column to trades")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        self.conn.commit()
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              TRADES
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_trade(self, trade: TradeRecord) -> int:
        """Add a new trade record"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO trades (
                token_mint, token_symbol, side, entry_price, exit_price,
                is_simulated, amount, sol_invested, sol_returned, pnl_sol, pnl_percent,
                token_score, sentiment_score, risk_score, ai_confidence,
                liquidity, volume_24h, holder_count, age_hours, top_10_percent,
                outcome, hold_time_hours, exit_reason, entry_time, exit_time, extra_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.token_mint, trade.token_symbol, trade.side, trade.entry_price, trade.exit_price,
            int(trade.is_simulated), trade.amount, trade.sol_invested, trade.sol_returned, trade.pnl_sol, trade.pnl_percent,
            trade.token_score, trade.sentiment_score, trade.risk_score, trade.ai_confidence,
            trade.liquidity, trade.volume_24h, trade.holder_count, trade.age_hours, trade.top_10_percent,
            trade.outcome, trade.hold_time_hours, trade.exit_reason, trade.entry_time, trade.exit_time,
            trade.extra_data
        ))
        
        self.conn.commit()
        trade_id = cursor.lastrowid
        logger.info(f"Trade #{trade_id} recorded: {trade.token_symbol} {trade.side}")
        return trade_id
    
    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        sol_returned: float,
        exit_reason: str = "MANUAL"
    ) -> Optional[TradeRecord]:
        """Close a trade and calculate PnL"""
        cursor = self.conn.cursor()
        
        # Get existing trade
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Calculate PnL
        entry_price = row["entry_price"]
        sol_invested = row["sol_invested"]
        pnl_sol = sol_returned - sol_invested
        pnl_percent = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        
        # Calculate hold time
        entry_time = datetime.fromisoformat(row["entry_time"])
        exit_time = datetime.now()
        hold_time_hours = (exit_time - entry_time).total_seconds() / 3600
        
        # Determine outcome
        outcome = "WIN" if pnl_sol > 0 else "LOSS"
        
        # Update record
        cursor.execute("""
            UPDATE trades SET
                exit_price = ?,
                sol_returned = ?,
                pnl_sol = ?,
                pnl_percent = ?,
                outcome = ?,
                hold_time_hours = ?,
                exit_reason = ?,
                exit_time = ?
            WHERE id = ?
        """, (
            exit_price, sol_returned, pnl_sol, pnl_percent,
            outcome, hold_time_hours, exit_reason, exit_time.isoformat(), trade_id
        ))
        
        self.conn.commit()
        logger.info(f"Trade #{trade_id} closed: {outcome} {pnl_percent:+.1f}% ({pnl_sol:+.4f} SOL)")
        
        return self.get_trade(trade_id)
    
    def get_trade(self, trade_id: int) -> Optional[TradeRecord]:
        """Get a trade by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return TradeRecord(
            id=row["id"],
            token_mint=row["token_mint"],
            token_symbol=row["token_symbol"],
            side=row["side"],
            entry_price=row["entry_price"],
            is_simulated=bool(row["is_simulated"]),
            exit_price=row["exit_price"],
            amount=row["amount"],
            sol_invested=row["sol_invested"],
            sol_returned=row["sol_returned"],
            pnl_sol=row["pnl_sol"],
            pnl_percent=row["pnl_percent"],
            token_score=row["token_score"],
            sentiment_score=row["sentiment_score"],
            risk_score=row["risk_score"],
            ai_confidence=row["ai_confidence"],
            liquidity=row["liquidity"],
            volume_24h=row["volume_24h"],
            holder_count=row["holder_count"],
            age_hours=row["age_hours"],
            top_10_percent=row["top_10_percent"],
            outcome=row["outcome"],
            hold_time_hours=row["hold_time_hours"],
            exit_reason=row["exit_reason"],
            entry_time=row["entry_time"],
            exit_time=row["exit_time"],
            extra_data=row["extra_data"]
        )
    
    def get_open_trades(self) -> list[TradeRecord]:
        """Get all open trades"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE outcome = 'OPEN' ORDER BY entry_time DESC")
        return [self._row_to_trade(row) for row in cursor.fetchall()]
    
    def get_recent_trades(self, limit: int = 50) -> list[TradeRecord]:
        """Get recent trades"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,))
        return [self._row_to_trade(row) for row in cursor.fetchall()]
    
    def _row_to_trade(self, row) -> TradeRecord:
        """Convert DB row to TradeRecord"""
        return TradeRecord(
            id=row["id"],
            token_mint=row["token_mint"],
            token_symbol=row["token_symbol"],
            side=row["side"],
            entry_price=row["entry_price"],
            is_simulated=bool(row["is_simulated"]),
            exit_price=row["exit_price"],
            amount=row["amount"],
            sol_invested=row["sol_invested"],
            sol_returned=row["sol_returned"],
            pnl_sol=row["pnl_sol"],
            pnl_percent=row["pnl_percent"],
            token_score=row["token_score"],
            sentiment_score=row["sentiment_score"],
            risk_score=row["risk_score"],
            ai_confidence=row["ai_confidence"],
            liquidity=row["liquidity"],
            volume_24h=row["volume_24h"],
            holder_count=row["holder_count"],
            age_hours=row["age_hours"],
            top_10_percent=row["top_10_percent"],
            outcome=row["outcome"],
            hold_time_hours=row["hold_time_hours"],
            exit_reason=row["exit_reason"],
            entry_time=row["entry_time"],
            exit_time=row["exit_time"],
            extra_data=row.get("extra_data"),
        )

    def get_seen_token_mints(self, limit: int = 500) -> Set[str]:
        """Return recently observed token mints from trades and scans."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT token_mint FROM trades ORDER BY entry_time DESC LIMIT ?",
            (limit,)
        )
        trade_mints = {row[0] for row in cursor.fetchall()}

        cursor.execute(
            "SELECT token_mint FROM scans ORDER BY scan_time DESC LIMIT ?",
            (limit,)
        )
        scan_mints = {row[0] for row in cursor.fetchall()}

        return trade_mints.union(scan_mints)

    def get_latest_open_trade_by_mint(self, token_mint: str) -> Optional[TradeRecord]:
        """Fetch most recent open trade for a token."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM trades
            WHERE token_mint = ? AND outcome = 'OPEN'
            ORDER BY entry_time DESC
            LIMIT 1
            """,
            (token_mint,)
        )
        row = cursor.fetchone()
        return self._row_to_trade(row) if row else None
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              SCANS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_scan(self, scan: TokenScan) -> int:
        """Record a token scan"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO scans (
                token_mint, token_symbol, scan_time, price, liquidity,
                volume_24h, holder_count, age_hours, ai_decision, ai_confidence,
                token_score, sentiment_score, risk_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scan.token_mint, scan.token_symbol, scan.scan_time, scan.price,
            scan.liquidity, scan.volume_24h, scan.holder_count, scan.age_hours,
            scan.ai_decision, scan.ai_confidence, scan.token_score,
            scan.sentiment_score, scan.risk_score
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def update_scan_outcome(self, scan_id: int, price_1h: float = None, price_24h: float = None, was_rug: bool = None):
        """Update scan with what happened later"""
        cursor = self.conn.cursor()
        
        updates = []
        params = []
        
        if price_1h is not None:
            updates.append("price_1h_later = ?")
            params.append(price_1h)
        if price_24h is not None:
            updates.append("price_24h_later = ?")
            params.append(price_24h)
        if was_rug is not None:
            updates.append("was_rug = ?")
            params.append(1 if was_rug else 0)
        
        if updates:
            params.append(scan_id)
            cursor.execute(f"UPDATE scans SET {', '.join(updates)} WHERE id = ?", params)
            self.conn.commit()
    
    def get_recent_scans(self, limit: int = 100) -> list[TokenScan]:
        """Get recent scans"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM scans ORDER BY scan_time DESC LIMIT ?", (limit,))
        return [self._row_to_scan(row) for row in cursor.fetchall()]
    
    def _row_to_scan(self, row) -> TokenScan:
        """Convert DB row to TokenScan"""
        return TokenScan(
            id=row["id"],
            token_mint=row["token_mint"],
            token_symbol=row["token_symbol"],
            scan_time=row["scan_time"],
            price=row["price"],
            liquidity=row["liquidity"],
            volume_24h=row["volume_24h"],
            holder_count=row["holder_count"],
            age_hours=row["age_hours"],
            ai_decision=row["ai_decision"],
            ai_confidence=row["ai_confidence"],
            token_score=row["token_score"],
            sentiment_score=row["sentiment_score"],
            risk_score=row["risk_score"],
            price_1h_later=row["price_1h_later"],
            price_24h_later=row["price_24h_later"],
            was_rug=bool(row["was_rug"]) if row["was_rug"] is not None else None
        )
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                           WHALE ALERTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_whale_alert(
        self,
        token_mint: str,
        token_symbol: str,
        whale_address: str,
        action: str,
        amount_usd: float,
        amount_tokens: float = None,
        signature: str = None
    ) -> int:
        """Record a whale alert"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO whale_alerts (
                token_mint, token_symbol, whale_address, action,
                amount_usd, amount_tokens, signature, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            token_mint, token_symbol, whale_address, action,
            amount_usd, amount_tokens, signature, datetime.now().isoformat()
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_whale_alerts(self, token_mint: str = None, hours: int = 24) -> list[dict]:
        """Get recent whale alerts"""
        cursor = self.conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        if token_mint:
            cursor.execute("""
                SELECT * FROM whale_alerts 
                WHERE token_mint = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (token_mint, since))
        else:
            cursor.execute("""
                SELECT * FROM whale_alerts 
                WHERE timestamp > ?
                ORDER BY timestamp DESC
            """, (since,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                              STATS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_stats(self, days: int = 7) -> dict:
        """Get trading stats for learning"""
        cursor = self.conn.cursor()
        
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Overall stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 'OPEN' THEN 1 ELSE 0 END) as open_trades,
                SUM(COALESCE(pnl_sol, 0)) as total_pnl,
                AVG(CASE WHEN outcome = 'WIN' THEN pnl_percent END) as avg_win_pct,
                AVG(CASE WHEN outcome = 'LOSS' THEN pnl_percent END) as avg_loss_pct,
                AVG(hold_time_hours) as avg_hold_time,
                MAX(pnl_sol) as best_trade,
                MIN(pnl_sol) as worst_trade
            FROM trades
            WHERE entry_time > ?
        """, (since,))
        
        row = cursor.fetchone()
        
        total = row["total_trades"] or 0
        wins = row["wins"] or 0
        losses = row["losses"] or 0
        
        return {
            "period_days": days,
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "open_trades": row["open_trades"] or 0,
            "win_rate": (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
            "total_pnl_sol": row["total_pnl"] or 0,
            "avg_win_percent": row["avg_win_pct"] or 0,
            "avg_loss_percent": row["avg_loss_pct"] or 0,
            "avg_hold_time_hours": row["avg_hold_time"] or 0,
            "best_trade_sol": row["best_trade"] or 0,
            "worst_trade_sol": row["worst_trade"] or 0
        }
    
    def get_learning_insights(self) -> dict:
        """
        Get insights for AI learning
        
        Analyzes past trades to find patterns:
        - What token_score range has best win rate?
        - What liquidity range works best?
        - What hold time is optimal?
        """
        cursor = self.conn.cursor()
        
        # Score range analysis
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN token_score >= 80 THEN '80-100'
                    WHEN token_score >= 60 THEN '60-79'
                    WHEN token_score >= 40 THEN '40-59'
                    ELSE '0-39'
                END as score_range,
                COUNT(*) as trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                AVG(pnl_percent) as avg_pnl
            FROM trades
            WHERE outcome != 'OPEN'
            GROUP BY score_range
        """)
        
        score_analysis = {}
        for row in cursor.fetchall():
            score_analysis[row["score_range"]] = {
                "trades": row["trades"],
                "wins": row["wins"],
                "win_rate": (row["wins"] / row["trades"] * 100) if row["trades"] > 0 else 0,
                "avg_pnl": row["avg_pnl"] or 0
            }
        
        # Liquidity range analysis
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN liquidity >= 500000 THEN '500k+'
                    WHEN liquidity >= 100000 THEN '100k-500k'
                    WHEN liquidity >= 50000 THEN '50k-100k'
                    ELSE '<50k'
                END as liq_range,
                COUNT(*) as trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                AVG(pnl_percent) as avg_pnl
            FROM trades
            WHERE outcome != 'OPEN'
            GROUP BY liq_range
        """)
        
        liquidity_analysis = {}
        for row in cursor.fetchall():
            liquidity_analysis[row["liq_range"]] = {
                "trades": row["trades"],
                "wins": row["wins"],
                "win_rate": (row["wins"] / row["trades"] * 100) if row["trades"] > 0 else 0,
                "avg_pnl": row["avg_pnl"] or 0
            }
        
        # Optimal hold time
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN hold_time_hours <= 1 THEN '<1h'
                    WHEN hold_time_hours <= 4 THEN '1-4h'
                    WHEN hold_time_hours <= 12 THEN '4-12h'
                    WHEN hold_time_hours <= 24 THEN '12-24h'
                    ELSE '24h+'
                END as hold_range,
                COUNT(*) as trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                AVG(pnl_percent) as avg_pnl
            FROM trades
            WHERE outcome != 'OPEN' AND hold_time_hours IS NOT NULL
            GROUP BY hold_range
        """)
        
        hold_time_analysis = {}
        for row in cursor.fetchall():
            hold_time_analysis[row["hold_range"]] = {
                "trades": row["trades"],
                "wins": row["wins"],
                "win_rate": (row["wins"] / row["trades"] * 100) if row["trades"] > 0 else 0,
                "avg_pnl": row["avg_pnl"] or 0
            }
        
        return {
            "score_analysis": score_analysis,
            "liquidity_analysis": liquidity_analysis,
            "hold_time_analysis": hold_time_analysis
        }
    
    def close(self):
        """Close database connection"""
        self.conn.close()


# Test
if __name__ == "__main__":
    db = Database()
    
    # Test trade
    trade = TradeRecord(
        id=None,
        token_mint="test123",
        token_symbol="TEST",
        side="BUY",
        entry_price=0.001,
        is_simulated=False,
        exit_price=None,
        amount=1000000,
        sol_invested=0.5,
        sol_returned=None,
        pnl_sol=None,
        pnl_percent=None,
        token_score=85,
        sentiment_score=70,
        risk_score=80,
        ai_confidence=90,
        liquidity=100000,
        volume_24h=50000,
        holder_count=500,
        age_hours=12,
        top_10_percent=25,
        outcome="OPEN",
        hold_time_hours=None,
        exit_reason=None,
        entry_time=datetime.now().isoformat(),
        exit_time=None
    )
    
    trade_id = db.add_trade(trade)
    print(f"Created trade #{trade_id}")
    
    # Close it
    db.close_trade(trade_id, exit_price=0.0015, sol_returned=0.75, exit_reason="TP")
    
    # Get stats
    stats = db.get_stats()
    print(f"\nStats: {stats}")
    
    db.close()
