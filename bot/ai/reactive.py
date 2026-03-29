"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                      NEXUS AI - Reactive Learning Engine                      ║
║                 Real-time learning from every trade result                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Unlike the batch LearningEngine that needs 50+ trades, this system:
1. Learns from EVERY trade immediately
2. Adjusts weights in real-time
3. Provides feedback to AI agents after each result
4. No minimum data threshold - starts learning from trade #1

This is true "reactive" AI that evolves with each decision.
"""

import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from loguru import logger


@dataclass
class RealtimeWeights:
    """Weights that adjust in real-time based on results"""
    
    # Token characteristics weights
    liquidity_weight: float = 1.0       # How much to trust liquidity
    holder_count_weight: float = 1.0    # How much to trust holder count
    age_weight: float = 1.0             # How much to trust token age
    volume_weight: float = 1.0          # How much to trust volume
    
    # AI agent trust weights
    token_analyzer_trust: float = 1.0   # Trust in Token Analyzer agent
    sentiment_trust: float = 1.0        # Trust in Sentiment agent
    risk_trust: float = 1.0             # Trust in Risk Assessor agent
    
    # Pattern weights (learned from results)
    whale_signal_weight: float = 1.0    # How much to trust whale signals
    low_mcap_bonus: float = 0.0         # Extra score for low mcap tokens
    high_volume_bonus: float = 0.0      # Extra score for high volume
    
    # Risk adjustments
    base_stop_loss: float = 15.0
    base_take_profit: float = 50.0
    position_size_multiplier: float = 1.0
    
    # Learning rate (how fast to adjust)
    learning_rate: float = 0.15  # 15% adjustment per trade
    
    # Stats
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0


@dataclass 
class TradeOutcome:
    """Outcome of a completed trade for learning"""
    token_mint: str
    pnl_percent: float
    hold_time_hours: float
    
    # What the AI saw at entry
    entry_liquidity: float
    entry_holders: int
    entry_age_hours: float
    entry_volume: float
    
    # AI scores at entry
    token_score: int
    sentiment_score: int
    risk_score: int
    confidence: int
    
    # Signals at entry
    had_whale_signal: bool = False
    whale_was_buying: bool = False


class ReactiveAI:
    """
    Real-time reactive learning system
    
    Core concept: Every trade outcome immediately adjusts the AI's behavior.
    - WIN → Reinforce the patterns that led to the decision
    - LOSS → Reduce trust in the signals that were present
    
    This creates a feedback loop where the AI literally learns from experience.
    """
    
    WEIGHTS_FILE = Path(__file__).parent.parent / "data_store" / "reactive_weights.json"
    HISTORY_FILE = Path(__file__).parent.parent / "training" / "trade_outcomes.json"
    
    def __init__(self):
        self.weights = self._load_weights()
        self.outcomes_history: list[dict] = self._load_history()
        
        logger.info(f"🧠 Reactive AI initialized (trades: {self.weights.total_trades}, "
                   f"win rate: {self._win_rate():.1f}%)")
    
    def _load_weights(self) -> RealtimeWeights:
        """Load weights from disk or create new"""
        if self.WEIGHTS_FILE.exists():
            try:
                with open(self.WEIGHTS_FILE, 'r') as f:
                    data = json.load(f)
                    return RealtimeWeights(**data)
            except Exception as e:
                logger.warning(f"Could not load weights: {e}")
        return RealtimeWeights()
    
    def _save_weights(self):
        """Save weights to disk"""
        self.WEIGHTS_FILE.parent.mkdir(exist_ok=True)
        with open(self.WEIGHTS_FILE, 'w') as f:
            json.dump({
                "liquidity_weight": self.weights.liquidity_weight,
                "holder_count_weight": self.weights.holder_count_weight,
                "age_weight": self.weights.age_weight,
                "volume_weight": self.weights.volume_weight,
                "token_analyzer_trust": self.weights.token_analyzer_trust,
                "sentiment_trust": self.weights.sentiment_trust,
                "risk_trust": self.weights.risk_trust,
                "whale_signal_weight": self.weights.whale_signal_weight,
                "low_mcap_bonus": self.weights.low_mcap_bonus,
                "high_volume_bonus": self.weights.high_volume_bonus,
                "base_stop_loss": self.weights.base_stop_loss,
                "base_take_profit": self.weights.base_take_profit,
                "position_size_multiplier": self.weights.position_size_multiplier,
                "learning_rate": self.weights.learning_rate,
                "total_trades": self.weights.total_trades,
                "wins": self.weights.wins,
                "losses": self.weights.losses,
                "total_pnl": self.weights.total_pnl
            }, f, indent=2)
    
    def _load_history(self) -> list[dict]:
        """Load outcome history"""
        if self.HISTORY_FILE.exists():
            try:
                with open(self.HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return []
    
    def _save_history(self):
        """Save outcome history"""
        self.HISTORY_FILE.parent.mkdir(exist_ok=True)
        with open(self.HISTORY_FILE, 'w') as f:
            json.dump(self.outcomes_history[-1000:], f, indent=2)  # Keep last 1000
    
    def _win_rate(self) -> float:
        """Calculate current win rate"""
        total = self.weights.wins + self.weights.losses
        if total == 0:
            return 50.0
        return (self.weights.wins / total) * 100
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                           CORE: LEARN FROM TRADE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def learn_from_trade(self, outcome: TradeOutcome):
        """
        THE HEART OF REACTIVE AI
        
        Called immediately when a trade closes.
        Adjusts all weights based on what worked/failed.
        """
        is_win = outcome.pnl_percent > 0
        lr = self.weights.learning_rate
        
        # Scale adjustment by how big the win/loss was
        magnitude = min(abs(outcome.pnl_percent) / 50, 2.0)  # Cap at 2x
        adjustment = lr * magnitude
        
        logger.info(f"🧠 Learning from {'WIN' if is_win else 'LOSS'}: {outcome.pnl_percent:+.1f}%")
        
        # ───────────────────────────────────────────────────────────────────────
        # ADJUST TOKEN CHARACTERISTIC WEIGHTS
        # ───────────────────────────────────────────────────────────────────────
        
        # Liquidity: Did high/low liquidity help?
        if outcome.entry_liquidity > 200_000:  # High liquidity
            if is_win:
                self.weights.liquidity_weight *= (1 + adjustment * 0.5)
            else:
                self.weights.liquidity_weight *= (1 - adjustment * 0.3)
        
        # Holder count
        if outcome.entry_holders > 500:  # Many holders
            if is_win:
                self.weights.holder_count_weight *= (1 + adjustment * 0.5)
            else:
                self.weights.holder_count_weight *= (1 - adjustment * 0.3)
        
        # Age: Young tokens riskier
        if outcome.entry_age_hours < 6:  # Very new
            if is_win:
                self.weights.age_weight *= (1 - adjustment * 0.2)  # Trust age less (new worked)
            else:
                self.weights.age_weight *= (1 + adjustment * 0.5)  # Trust age more (new failed)
        
        # Volume
        if outcome.entry_volume > 100_000:
            if is_win:
                self.weights.high_volume_bonus += adjustment * 5
            else:
                self.weights.high_volume_bonus -= adjustment * 3
        
        # ───────────────────────────────────────────────────────────────────────
        # ADJUST AGENT TRUST
        # ───────────────────────────────────────────────────────────────────────
        
        # Which agent was most confident about this trade?
        scores = [
            (outcome.token_score, "token_analyzer_trust"),
            (outcome.sentiment_score, "sentiment_trust"),
            (outcome.risk_score, "risk_trust")
        ]
        
        for score, attr in scores:
            if score >= 80:  # This agent was very confident
                current = getattr(self.weights, attr)
                if is_win:
                    setattr(self.weights, attr, current * (1 + adjustment * 0.3))
                else:
                    setattr(self.weights, attr, current * (1 - adjustment * 0.2))
        
        # ───────────────────────────────────────────────────────────────────────
        # ADJUST WHALE SIGNAL TRUST
        # ───────────────────────────────────────────────────────────────────────
        
        if outcome.had_whale_signal:
            if outcome.whale_was_buying:
                if is_win:
                    self.weights.whale_signal_weight *= (1 + adjustment * 0.5)
                    logger.info("   📈 Whale BUY signal validated! Increasing trust.")
                else:
                    self.weights.whale_signal_weight *= (1 - adjustment * 0.3)
                    logger.info("   📉 Whale BUY signal failed. Reducing trust.")
        
        # ───────────────────────────────────────────────────────────────────────
        # ADJUST RISK PARAMETERS
        # ───────────────────────────────────────────────────────────────────────
        
        if is_win:
            # Won - maybe we can be more aggressive?
            if outcome.pnl_percent > self.weights.base_take_profit:
                # TP was too tight, we could have held longer
                self.weights.base_take_profit *= (1 + adjustment * 0.1)
            
            self.weights.position_size_multiplier = min(
                self.weights.position_size_multiplier * (1 + adjustment * 0.1),
                2.0  # Max 2x position size
            )
        else:
            # Lost - be more conservative
            if abs(outcome.pnl_percent) > self.weights.base_stop_loss:
                # SL was too loose
                self.weights.base_stop_loss *= (1 - adjustment * 0.1)
            
            self.weights.position_size_multiplier = max(
                self.weights.position_size_multiplier * (1 - adjustment * 0.1),
                0.5  # Min 0.5x position size
            )
        
        # ───────────────────────────────────────────────────────────────────────
        # UPDATE STATS
        # ───────────────────────────────────────────────────────────────────────
        
        self.weights.total_trades += 1
        if is_win:
            self.weights.wins += 1
        else:
            self.weights.losses += 1
        self.weights.total_pnl += outcome.pnl_percent
        
        # Clamp weights to reasonable bounds
        self._clamp_weights()
        
        # Save
        self._save_weights()
        self._record_outcome(outcome)
        
        self._log_status()
    
    def _clamp_weights(self):
        """Keep weights in reasonable bounds"""
        w = self.weights
        
        # Characteristic weights: 0.3 to 3.0
        w.liquidity_weight = max(0.3, min(3.0, w.liquidity_weight))
        w.holder_count_weight = max(0.3, min(3.0, w.holder_count_weight))
        w.age_weight = max(0.3, min(3.0, w.age_weight))
        w.volume_weight = max(0.3, min(3.0, w.volume_weight))
        
        # Agent trust: 0.5 to 2.0
        w.token_analyzer_trust = max(0.5, min(2.0, w.token_analyzer_trust))
        w.sentiment_trust = max(0.5, min(2.0, w.sentiment_trust))
        w.risk_trust = max(0.5, min(2.0, w.risk_trust))
        
        # Whale signal: 0.0 to 3.0
        w.whale_signal_weight = max(0.0, min(3.0, w.whale_signal_weight))
        
        # Bonuses: -20 to +20
        w.low_mcap_bonus = max(-20, min(20, w.low_mcap_bonus))
        w.high_volume_bonus = max(-20, min(20, w.high_volume_bonus))
        
        # Risk params
        w.base_stop_loss = max(5, min(30, w.base_stop_loss))
        w.base_take_profit = max(20, min(100, w.base_take_profit))
    
    def _record_outcome(self, outcome: TradeOutcome):
        """Record outcome to history"""
        self.outcomes_history.append({
            "timestamp": datetime.now().isoformat(),
            "token": outcome.token_mint[:8],
            "pnl": outcome.pnl_percent,
            "hold_hours": outcome.hold_time_hours,
            "liquidity": outcome.entry_liquidity,
            "scores": {
                "token": outcome.token_score,
                "sentiment": outcome.sentiment_score,
                "risk": outcome.risk_score
            }
        })
        self._save_history()
    
    def _log_status(self):
        """Log current AI status"""
        w = self.weights
        logger.info(f"   Stats: {w.wins}W/{w.losses}L ({self._win_rate():.0f}%), "
                   f"PnL: {w.total_pnl:+.1f}%")
        logger.info(f"   Trust: Token={w.token_analyzer_trust:.2f}, "
                   f"Sentiment={w.sentiment_trust:.2f}, Risk={w.risk_trust:.2f}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    #                           APPLY WEIGHTS TO DECISIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def adjust_scores(
        self,
        token_score: int,
        sentiment_score: int, 
        risk_score: int,
        token_data: dict
    ) -> tuple[int, int, int, int]:
        """
        Adjust AI scores based on learned weights
        
        Returns:
            (adjusted_token, adjusted_sentiment, adjusted_risk, bonus)
        """
        w = self.weights
        
        # Apply agent trust weights
        adj_token = int(token_score * w.token_analyzer_trust)
        adj_sentiment = int(sentiment_score * w.sentiment_trust)
        adj_risk = int(risk_score * w.risk_trust)
        
        # Calculate bonus from learned patterns
        bonus = 0
        
        if token_data.get("volume_24h", 0) > 100_000:
            bonus += w.high_volume_bonus
        
        if token_data.get("market_cap", 0) < 500_000:
            bonus += w.low_mcap_bonus
        
        # Whale signal bonus
        if token_data.get("whale_signal") in ["BUY", "STRONG_BUY"]:
            bonus += 10 * w.whale_signal_weight
        elif token_data.get("whale_signal") in ["SELL", "STRONG_SELL"]:
            bonus -= 10 * w.whale_signal_weight
        
        # Clamp scores
        adj_token = max(0, min(100, adj_token))
        adj_sentiment = max(0, min(100, adj_sentiment))
        adj_risk = max(0, min(100, adj_risk))
        bonus = max(-30, min(30, int(bonus)))
        
        return adj_token, adj_sentiment, adj_risk, bonus
    
    def get_position_size(self, base_size: float) -> float:
        """Get adjusted position size based on learning"""
        return base_size * self.weights.position_size_multiplier
    
    def get_sl_tp(self) -> tuple[float, float]:
        """Get adjusted stop loss and take profit"""
        return self.weights.base_stop_loss, self.weights.base_take_profit
    
    def should_take_trade(self, final_score: int, confidence: int) -> tuple[bool, str]:
        """
        Final check based on recent performance
        
        If we're on a losing streak, be more conservative.
        If winning, be more aggressive.
        """
        # Check recent performance
        recent = self.outcomes_history[-5:]  # Last 5 trades
        if len(recent) >= 3:
            recent_losses = sum(1 for o in recent if o.get("pnl", 0) < 0)
            
            if recent_losses >= 3:
                # Losing streak - require higher confidence
                min_conf = 85
                if confidence < min_conf:
                    return False, f"Losing streak: require {min_conf}% confidence"
            
            recent_wins = sum(1 for o in recent if o.get("pnl", 0) > 0)
            if recent_wins >= 4:
                # Hot streak - can be more aggressive
                return True, "Hot streak: taking trade"
        
        return True, "Normal conditions"
    
    def get_feedback_prompt(self) -> str:
        """
        Generate context for AI agents based on learning
        
        This is injected into agent prompts to make them aware of
        what's been working/failing.
        """
        w = self.weights
        
        if w.total_trades < 3:
            return ""  # Not enough data yet
        
        feedback = "\n\n--- LEARNING FEEDBACK ---\n"
        feedback += f"Performance: {w.wins}W/{w.losses}L ({self._win_rate():.0f}% win rate)\n"
        
        # Tell AI what's working
        if w.token_analyzer_trust > 1.2:
            feedback += "✓ Token analysis has been ACCURATE - trust it more\n"
        elif w.token_analyzer_trust < 0.8:
            feedback += "⚠ Token analysis has been UNRELIABLE - be skeptical\n"
        
        if w.sentiment_trust > 1.2:
            feedback += "✓ Sentiment signals have been ACCURATE\n"
        elif w.sentiment_trust < 0.8:
            feedback += "⚠ Sentiment signals have been UNRELIABLE\n"
        
        if w.whale_signal_weight > 1.5:
            feedback += "✓ Whale signals are STRONG indicators - weight heavily\n"
        elif w.whale_signal_weight < 0.5:
            feedback += "⚠ Whale signals have been MISLEADING - ignore them\n"
        
        if w.high_volume_bonus > 5:
            feedback += f"✓ High volume tokens have performed well (+{w.high_volume_bonus:.0f} bonus)\n"
        elif w.high_volume_bonus < -5:
            feedback += f"⚠ High volume tokens have UNDERPERFORMED\n"
        
        feedback += "--- END FEEDBACK ---\n"
        
        return feedback


# Test
if __name__ == "__main__":
    ai = ReactiveAI()
    
    # Simulate a winning trade
    win = TradeOutcome(
        token_mint="test123",
        pnl_percent=45.0,
        hold_time_hours=2.5,
        entry_liquidity=150_000,
        entry_holders=800,
        entry_age_hours=4,
        entry_volume=200_000,
        token_score=85,
        sentiment_score=70,
        risk_score=90,
        confidence=88,
        had_whale_signal=True,
        whale_was_buying=True
    )
    
    print("\n=== SIMULATING WIN ===")
    ai.learn_from_trade(win)
    
    # Simulate a losing trade
    loss = TradeOutcome(
        token_mint="test456",
        pnl_percent=-18.0,
        hold_time_hours=0.5,
        entry_liquidity=40_000,
        entry_holders=200,
        entry_age_hours=1,
        entry_volume=30_000,
        token_score=72,
        sentiment_score=80,
        risk_score=65,
        confidence=75,
        had_whale_signal=False,
        whale_was_buying=False
    )
    
    print("\n=== SIMULATING LOSS ===")
    ai.learn_from_trade(loss)
    
    print("\n=== FEEDBACK FOR AI ===")
    print(ai.get_feedback_prompt())
