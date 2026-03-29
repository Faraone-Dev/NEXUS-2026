"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        NEXUS AI - Scan Updater                                ║
║              Updates historical scans with price data for learning            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This job runs periodically to:
1. Find scans from 1h ago → update price_1h_later
2. Find scans from 24h ago → update price_24h_later  
3. Detect rugs (price dropped 90%+)

This data is CRITICAL for the learning engine to analyze:
- Which tokens the AI skipped that pumped (missed opportunities)
- Which tokens the AI skipped that rugged (good decisions)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from .database import Database
from .jupiter import JupiterClient
from .birdeye import BirdeyeClient


class ScanUpdater:
    """
    Updates historical token scans with price data
    
    Essential for learning from both:
    - Trades taken (already tracked in trades table)
    - Trades SKIPPED (this is what we're tracking here)
    """
    
    def __init__(self, db: Database = None, requester=None):
        self.db = db or Database()
        self.jupiter = JupiterClient()
        self.birdeye = BirdeyeClient()
        self._requester = requester

    async def _call(self, api_name: str, func, *args, **kwargs):
        if self._requester:
            return await self._requester(api_name, func, *args, **kwargs)
        return await func(*args, **kwargs)

    def _fetch_scans_without_price(self, start: str, end: str, limit: int, column: str) -> list[dict]:
        """Synchronous helper to fetch scans missing given price columns."""
        if column not in {"price_1h_later", "price_24h_later"}:
            raise ValueError("Invalid column for scan fetch")
        cursor = self.db.conn.cursor()
        query = f"""
            SELECT id, token_mint, token_symbol, price
            FROM scans
            WHERE scan_time BETWEEN ? AND ?
              AND {column} IS NULL
            LIMIT ?
        """
        cursor.execute(query, (start, end, limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def _apply_1h_updates(self, updates: list[tuple[int, float, bool]]):
        if not updates:
            return
        cursor = self.db.conn.cursor()
        cursor.executemany(
            """
            UPDATE scans
            SET price_1h_later = ?, was_rug = ?
            WHERE id = ?
            """,
            [(price, 1 if was_rug else 0, scan_id) for scan_id, price, was_rug in updates]
        )
        self.db.conn.commit()

    def _apply_24h_updates(self, updates: list[tuple[int, float, Optional[int]]]):
        if not updates:
            return
        cursor = self.db.conn.cursor()
        for scan_id, price, was_rug in updates:
            if was_rug is not None:
                cursor.execute(
                    """
                    UPDATE scans
                    SET price_24h_later = ?, was_rug = COALESCE(was_rug, ?)
                    WHERE id = ?
                    """,
                    (price, was_rug, scan_id)
                )
            else:
                cursor.execute(
                    """
                    UPDATE scans SET price_24h_later = ? WHERE id = ?
                    """,
                    (price, scan_id)
                )
        self.db.conn.commit()

    def _fetch_learning_summary_rows(self) -> list[dict]:
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT 
                ai_decision,
                COUNT(*) as count,
                AVG(CASE WHEN price_1h_later > price THEN 
                    ((price_1h_later - price) / price * 100) 
                END) as avg_gain_1h,
                AVG(CASE WHEN price_1h_later < price THEN 
                    ((price - price_1h_later) / price * 100) 
                END) as avg_loss_1h,
                SUM(CASE WHEN was_rug = 1 THEN 1 ELSE 0 END) as rugs
            FROM scans
            WHERE price_1h_later IS NOT NULL
            GROUP BY ai_decision
            """
        )
        return [dict(row) for row in cursor.fetchall()]
        
    async def update_1h_prices(self, batch_size: int = 50) -> int:
        """
        Update price_1h_later for scans from ~1 hour ago
        
        Returns:
            Number of scans updated
        """
        now = datetime.now()
        start = (now - timedelta(minutes=65)).isoformat()
        end = (now - timedelta(minutes=55)).isoformat()
        scans = await asyncio.to_thread(
            self._fetch_scans_without_price,
            start,
            end,
            batch_size,
            "price_1h_later"
        )
        
        if not scans:
            return 0
        
        # Get all token mints
        mints = [s["token_mint"] for s in scans]
        
        # Batch fetch prices
        prices = await self._call("jupiter", self.jupiter.get_prices, mints) or {}
        
        # Update each scan
        updates = []
        for scan in scans:
            mint = scan["token_mint"]
            if mint in prices:
                current_price = prices[mint]
                original_price = scan["price"]
                
                # Check if it's a rug (dropped 90%+)
                was_rug = False
                if original_price and original_price > 0:
                    drop_percent = ((original_price - current_price) / original_price) * 100
                    was_rug = drop_percent >= 90
                updates.append((scan["id"], current_price, was_rug))

        if not updates:
            return 0

        await asyncio.to_thread(self._apply_1h_updates, updates)
        logger.info(f"📊 Updated {len(updates)} scans with 1h price data")
        return len(updates)
    
    async def update_24h_prices(self, batch_size: int = 50) -> int:
        """
        Update price_24h_later for scans from ~24 hours ago
        
        Returns:
            Number of scans updated
        """
        now = datetime.now()
        start = (now - timedelta(hours=24, minutes=30)).isoformat()
        end = (now - timedelta(hours=23, minutes=30)).isoformat()
        scans = await asyncio.to_thread(
            self._fetch_scans_without_price,
            start,
            end,
            batch_size,
            "price_24h_later"
        )
        
        if not scans:
            return 0
        
        mints = [s["token_mint"] for s in scans]
        prices = await self._call("jupiter", self.jupiter.get_prices, mints) or {}
        
        updates = []
        for scan in scans:
            mint = scan["token_mint"]
            if mint in prices:
                current_price = prices[mint]
                original_price = scan["price"]
                
                # Update rug status if not already set
                was_rug = None
                if original_price and original_price > 0:
                    drop_percent = ((original_price - current_price) / original_price) * 100
                    if drop_percent >= 90:
                        was_rug = 1
                updates.append((scan["id"], current_price, was_rug))

        if not updates:
            return 0

        await asyncio.to_thread(self._apply_24h_updates, updates)
        logger.info(f"📊 Updated {len(updates)} scans with 24h price data")
        return len(updates)
    
    async def run_once(self) -> dict:
        """
        Run one update cycle
        
        Returns:
            Stats dict
        """
        updated_1h = await self.update_1h_prices()
        updated_24h = await self.update_24h_prices()
        
        return {
            "updated_1h": updated_1h,
            "updated_24h": updated_24h,
            "total": updated_1h + updated_24h
        }
    
    async def run_loop(self, interval_minutes: int = 5):
        """
        Run update loop continuously
        
        Args:
            interval_minutes: How often to check for updates
        """
        logger.info(f"🔄 Scan updater started (interval: {interval_minutes}min)")
        
        while True:
            try:
                stats = await self.run_once()
                if stats["total"] > 0:
                    logger.info(f"Updated: {stats['updated_1h']} (1h), {stats['updated_24h']} (24h)")
            except Exception as e:
                logger.error(f"Scan updater error: {e}")
            
            await asyncio.sleep(interval_minutes * 60)
    
    async def get_learning_summary(self) -> dict:
        """
        Get summary of what we can learn from updated scans
        
        Returns:
            Dict with insights
        """
        rows = await asyncio.to_thread(self._fetch_learning_summary_rows)
        results = {}
        for row in rows:
            results[row["ai_decision"]] = {
                "count": row["count"],
                "avg_gain_1h": row["avg_gain_1h"] or 0,
                "avg_loss_1h": row["avg_loss_1h"] or 0,
                "rugs": row["rugs"]
            }
        
        return results
    
    async def close(self):
        """Close connections"""
        await self.jupiter.close()
        await self.birdeye.close()


async def main():
    """Test the scan updater"""
    updater = ScanUpdater()
    
    print("=" * 50)
    print("SCAN UPDATER TEST")
    print("=" * 50)
    
    # Run once
    stats = await updater.run_once()
    print(f"\nUpdated: {stats}")
    
    # Get learning summary
    summary = await updater.get_learning_summary()
    print(f"\nLearning Summary:")
    for decision, data in summary.items():
        print(f"  {decision}: {data['count']} tokens, avg gain 1h: {data['avg_gain_1h']:.1f}%, rugs: {data['rugs']}")
    
    await updater.close()


if __name__ == "__main__":
    asyncio.run(main())
