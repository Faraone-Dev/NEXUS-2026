"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          NEXUS AI - Learning Engine                           ║
║                    Auto-tuning based on trade history                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
from loguru import logger
from pathlib import Path


@dataclass
class LearningInsights:
    """Insights derived from trade history"""
    
    # Optimal ranges found
    optimal_token_score_min: int
    optimal_liquidity_min: float
    optimal_liquidity_max: float
    optimal_holder_count_min: int
    optimal_age_hours_min: float
    optimal_age_hours_max: float
    
    # Risk adjustments
    suggested_stop_loss: float
    suggested_take_profit: float
    suggested_position_size: float
    
    # Pattern insights
    best_entry_hours: list[int]  # Hours of day with best results
    avoid_tokens_with: list[str]  # Patterns to avoid
    
    # Confidence
    data_points: int
    confidence_level: str  # LOW / MEDIUM / HIGH


class LearningEngine:
    """
    AI Learning Engine
    
    Analyzes trade history to:
    1. Find optimal entry parameters
    2. Adjust risk management
    3. Improve AI prompts
    4. Identify winning patterns
    """
    
    def __init__(self, db=None):
        # Import here to avoid circular imports
        if db is None:
            from .database import Database
            self.db = Database()
        else:
            self.db = db
        
        self.insights_file = Path(__file__).parent.parent / "data_store" / "learning_insights.json"
        self.insights: Optional[LearningInsights] = None
        
        self._load_insights()
        logger.info("🧠 Learning Engine initialized")
    
    def _load_insights(self):
        """Load saved insights"""
        if self.insights_file.exists():
            try:
                with open(self.insights_file, 'r') as f:
                    data = json.load(f)
                    self.insights = LearningInsights(**data)
                    logger.info(f"Loaded insights ({self.insights.data_points} data points)")
            except Exception as e:
                logger.warning(f"Could not load insights: {e}")
    
    def _save_insights(self):
        """Save insights to disk"""
        if self.insights:
            self.insights_file.parent.mkdir(exist_ok=True)
            with open(self.insights_file, 'w') as f:
                json.dump({
                    "optimal_token_score_min": self.insights.optimal_token_score_min,
                    "optimal_liquidity_min": self.insights.optimal_liquidity_min,
                    "optimal_liquidity_max": self.insights.optimal_liquidity_max,
                    "optimal_holder_count_min": self.insights.optimal_holder_count_min,
                    "optimal_age_hours_min": self.insights.optimal_age_hours_min,
                    "optimal_age_hours_max": self.insights.optimal_age_hours_max,
                    "suggested_stop_loss": self.insights.suggested_stop_loss,
                    "suggested_take_profit": self.insights.suggested_take_profit,
                    "suggested_position_size": self.insights.suggested_position_size,
                    "best_entry_hours": self.insights.best_entry_hours,
                    "avoid_tokens_with": self.insights.avoid_tokens_with,
                    "data_points": self.insights.data_points,
                    "confidence_level": self.insights.confidence_level
                }, f, indent=2)
    
    def analyze_and_learn(self) -> LearningInsights:
        """
        Analyze all trade history and extract insights
        
        Returns:
            LearningInsights with optimized parameters
        """
        logger.info("🧠 Running learning analysis...")
        
        # Get stats and insights from DB
        stats = self.db.get_stats(days=30)
        db_insights = self.db.get_learning_insights()
        
        total_trades = stats["total_trades"]
        
        if total_trades < 5:
            logger.warning("Not enough trades for learning (<5)")
            return self._get_default_insights()
        
        # Analyze score ranges
        score_analysis = db_insights.get("score_analysis", {})
        best_score_range = self._find_best_range(score_analysis)
        
        # Analyze liquidity ranges
        liq_analysis = db_insights.get("liquidity_analysis", {})
        best_liq_range = self._find_best_range(liq_analysis)
        
        # Analyze hold times
        hold_analysis = db_insights.get("hold_time_analysis", {})
        best_hold_range = self._find_best_range(hold_analysis)
        
        # Calculate optimal parameters
        optimal_token_score = self._range_to_min_score(best_score_range)
        optimal_liq_min, optimal_liq_max = self._range_to_liquidity(best_liq_range)
        
        # Analyze PnL distribution for risk management
        avg_win = abs(stats.get("avg_win_percent", 50))
        avg_loss = abs(stats.get("avg_loss_percent", -15))
        
        # Suggest SL/TP based on actual results
        suggested_sl = min(avg_loss * 1.2, 25)  # 20% buffer, max 25%
        suggested_tp = max(avg_win * 0.8, 30)   # 20% conservative, min 30%
        
        # Position sizing based on win rate
        win_rate = stats.get("win_rate", 50)
        if win_rate >= 60:
            suggested_position = 7  # More aggressive
        elif win_rate >= 50:
            suggested_position = 5  # Standard
        else:
            suggested_position = 3  # Conservative
        
        # Analyze entry timing (would need entry_time hour data)
        best_hours = self._analyze_entry_hours()
        
        # Identify patterns to avoid
        avoid_patterns = self._identify_losing_patterns()
        
        # Determine confidence level
        if total_trades >= 50:
            confidence = "HIGH"
        elif total_trades >= 20:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        self.insights = LearningInsights(
            optimal_token_score_min=optimal_token_score,
            optimal_liquidity_min=optimal_liq_min,
            optimal_liquidity_max=optimal_liq_max,
            optimal_holder_count_min=100,
            optimal_age_hours_min=1,
            optimal_age_hours_max=48,
            suggested_stop_loss=suggested_sl,
            suggested_take_profit=suggested_tp,
            suggested_position_size=suggested_position,
            best_entry_hours=best_hours,
            avoid_tokens_with=avoid_patterns,
            data_points=total_trades,
            confidence_level=confidence
        )
        
        self._save_insights()
        self._log_insights()
        
        return self.insights
    
    def _find_best_range(self, analysis: dict) -> Optional[str]:
        """Find the range with best win rate and PnL"""
        if not analysis:
            return None
        
        best_range = None
        best_score = -999
        
        for range_name, data in analysis.items():
            trades = data.get("trades", 0)
            if trades < 3:
                continue
            
            win_rate = data.get("win_rate", 0)
            avg_pnl = data.get("avg_pnl", 0)
            
            # Score combines win rate and PnL
            score = (win_rate * 0.6) + (avg_pnl * 0.4)
            
            if score > best_score:
                best_score = score
                best_range = range_name
        
        return best_range
    
    def _range_to_min_score(self, range_str: Optional[str]) -> int:
        """Convert score range string to minimum score"""
        if not range_str:
            return 70
        
        mapping = {
            "80-100": 80,
            "60-79": 60,
            "40-59": 50,
            "0-39": 40
        }
        return mapping.get(range_str, 70)
    
    def _range_to_liquidity(self, range_str: Optional[str]) -> tuple[float, float]:
        """Convert liquidity range string to min/max"""
        if not range_str:
            return 50_000, 1_000_000
        
        mapping = {
            "500k+": (500_000, 10_000_000),
            "100k-500k": (100_000, 500_000),
            "50k-100k": (50_000, 100_000),
            "<50k": (25_000, 50_000)
        }
        return mapping.get(range_str, (50_000, 1_000_000))
    
    def _analyze_entry_hours(self) -> list[int]:
        """Analyze which hours have best results from actual trade data"""
        cursor = self.db.conn.cursor()
        
        # Get hour-by-hour performance
        cursor.execute("""
            SELECT 
                CAST(strftime('%H', entry_time) AS INTEGER) as hour,
                COUNT(*) as trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                AVG(pnl_percent) as avg_pnl
            FROM trades
            WHERE outcome != 'OPEN' AND entry_time IS NOT NULL
            GROUP BY hour
            HAVING trades >= 2
            ORDER BY avg_pnl DESC
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            # Default to US market hours if no data
            return [14, 15, 16, 17, 18, 19, 20]
        
        # Return top performing hours (positive avg PnL)
        best_hours = []
        for row in rows:
            if row[3] and row[3] > 0:  # avg_pnl > 0
                best_hours.append(row[0])
        
        # If no positive hours, return top 5 by win rate
        if not best_hours:
            cursor.execute("""
                SELECT 
                    CAST(strftime('%H', entry_time) AS INTEGER) as hour,
                    AVG(CASE WHEN outcome = 'WIN' THEN 1.0 ELSE 0.0 END) as win_rate
                FROM trades
                WHERE outcome != 'OPEN' AND entry_time IS NOT NULL
                GROUP BY hour
                ORDER BY win_rate DESC
                LIMIT 5
            """)
            best_hours = [row[0] for row in cursor.fetchall()]
        
        return best_hours if best_hours else [14, 15, 16, 17, 18, 19, 20]
    
    def _identify_losing_patterns(self) -> list[str]:
        """Identify patterns that lead to losses"""
        patterns = []
        
        cursor = self.db.conn.cursor()
        
        # Check if low holder count correlates with losses
        cursor.execute("""
            SELECT 
                AVG(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as loss_rate
            FROM trades
            WHERE holder_count < 100 AND outcome != 'OPEN'
        """)
        row = cursor.fetchone()
        if row and row[0] and row[0] > 0.6:
            patterns.append("holder_count < 100")
        
        # Check if high top_10_percent correlates with losses
        cursor.execute("""
            SELECT 
                AVG(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as loss_rate
            FROM trades
            WHERE top_10_percent > 50 AND outcome != 'OPEN'
        """)
        row = cursor.fetchone()
        if row and row[0] and row[0] > 0.6:
            patterns.append("top_10_holders > 50%")
        
        # Check if very new tokens correlate with losses
        cursor.execute("""
            SELECT 
                AVG(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as loss_rate
            FROM trades
            WHERE age_hours < 1 AND outcome != 'OPEN'
        """)
        row = cursor.fetchone()
        if row and row[0] and row[0] > 0.6:
            patterns.append("age < 1 hour")
        
        return patterns
    
    def _get_default_insights(self) -> LearningInsights:
        """Get default insights when not enough data"""
        return LearningInsights(
            optimal_token_score_min=70,
            optimal_liquidity_min=50_000,
            optimal_liquidity_max=1_000_000,
            optimal_holder_count_min=100,
            optimal_age_hours_min=1,
            optimal_age_hours_max=48,
            suggested_stop_loss=15,
            suggested_take_profit=50,
            suggested_position_size=5,
            best_entry_hours=[14, 15, 16, 17, 18, 19, 20],
            avoid_tokens_with=[],
            data_points=0,
            confidence_level="LOW"
        )
    
    def _log_insights(self):
        """Log current insights"""
        if not self.insights:
            return
        
        logger.info("=" * 50)
        logger.info("🧠 LEARNING INSIGHTS")
        logger.info("=" * 50)
        logger.info(f"Data Points: {self.insights.data_points}")
        logger.info(f"Confidence: {self.insights.confidence_level}")
        logger.info("")
        logger.info("📊 Optimal Parameters:")
        logger.info(f"  Token Score: >= {self.insights.optimal_token_score_min}")
        logger.info(f"  Liquidity: ${self.insights.optimal_liquidity_min:,.0f} - ${self.insights.optimal_liquidity_max:,.0f}")
        logger.info(f"  Holders: >= {self.insights.optimal_holder_count_min}")
        logger.info("")
        logger.info("💰 Risk Management:")
        logger.info(f"  Stop Loss: {self.insights.suggested_stop_loss:.1f}%")
        logger.info(f"  Take Profit: {self.insights.suggested_take_profit:.1f}%")
        logger.info(f"  Position Size: {self.insights.suggested_position_size:.1f}%")
        logger.info("")
        if self.insights.avoid_tokens_with:
            logger.info("⚠️ Avoid Patterns:")
            for pattern in self.insights.avoid_tokens_with:
                logger.info(f"  - {pattern}")
        logger.info("=" * 50)
    
    def get_enhanced_prompt_context(self) -> str:
        """
        Generate context for AI prompts based on learning
        
        This can be injected into AI agent prompts to make them
        aware of historical performance patterns.
        """
        if not self.insights or self.insights.confidence_level == "LOW":
            return ""
        
        context = """
LEARNING CONTEXT (from historical trades):
"""
        
        context += f"""
- Tokens with score >= {self.insights.optimal_token_score_min} have performed best
- Optimal liquidity range: ${self.insights.optimal_liquidity_min:,.0f} - ${self.insights.optimal_liquidity_max:,.0f}
- Best results with >= {self.insights.optimal_holder_count_min} holders
"""
        
        if self.insights.avoid_tokens_with:
            context += "\nAVOID these patterns (historically losing):\n"
            for pattern in self.insights.avoid_tokens_with:
                context += f"- {pattern}\n"
        
        return context
    
    def should_override_ai_decision(self, token_data: dict, ai_decision: str) -> tuple[bool, str]:
        """
        Check if learning insights should override AI decision
        
        Returns:
            (should_override, reason)
        """
        if not self.insights or self.insights.confidence_level == "LOW":
            return False, ""
        
        # Only override if confidence is HIGH
        if self.insights.confidence_level != "HIGH":
            return False, ""
        
        # Check for avoid patterns
        for pattern in self.insights.avoid_tokens_with:
            if "holder_count < 100" in pattern:
                if token_data.get("holder_count", 0) < 100:
                    return True, "Learning: Low holder count historically loses"
            
            if "top_10_holders > 50%" in pattern:
                if token_data.get("top_10_percent", 0) > 50:
                    return True, "Learning: High concentration historically loses"
            
            if "age < 1 hour" in pattern:
                if token_data.get("age_hours", 0) < 1:
                    return True, "Learning: Very new tokens historically lose"
        
        return False, ""
    
    def get_adjusted_position_size(self, base_size: float, token_score: int) -> float:
        """
        Adjust position size based on learning
        
        Higher score = can be more aggressive (if learning supports it)
        """
        if not self.insights or self.insights.confidence_level == "LOW":
            return base_size
        
        suggested = self.insights.suggested_position_size
        
        # Adjust based on token score relative to optimal
        optimal_min = self.insights.optimal_token_score_min
        
        if token_score >= optimal_min + 10:
            # Very good score - can be slightly more aggressive
            return min(suggested * 1.2, 10)
        elif token_score >= optimal_min:
            # Good score - use suggested
            return suggested
        else:
            # Below optimal - be conservative
            return suggested * 0.7
    
    def get_adjusted_sl_tp(self) -> tuple[float, float]:
        """Get adjusted stop loss and take profit from learning"""
        if not self.insights:
            return 15.0, 50.0
        
        return self.insights.suggested_stop_loss, self.insights.suggested_take_profit


# Test
if __name__ == "__main__":
    from database import Database
    
    db = Database()
    engine = LearningEngine(db)
    
    insights = engine.analyze_and_learn()
    
    print("\n" + "=" * 50)
    print("LEARNING TEST COMPLETE")
    print("=" * 50)
    
    # Test enhanced prompt
    context = engine.get_enhanced_prompt_context()
    if context:
        print("\nEnhanced AI Context:")
        print(context)
    
    db.close()
