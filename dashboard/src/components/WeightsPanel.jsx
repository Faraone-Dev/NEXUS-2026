function WeightBar({ label, value, max = 2.0 }) {
  const pct = Math.min(100, (value / max) * 100)
  const color = value > 1.2 ? 'bg-[var(--green)]' : value < 0.8 ? 'bg-[var(--red)]' : 'bg-[var(--blue)]'

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-[var(--text-muted)]">{label}</span>
        <span className="font-mono font-bold">{value.toFixed(3)}</span>
      </div>
      <div className="h-2 bg-[var(--bg-hover)] rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function WeightsPanel({ weights }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Trust weights */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-5 space-y-4">
        <h3 className="text-sm font-bold uppercase text-[var(--text-muted)] tracking-wide">Agent Trust Weights</h3>
        <WeightBar label="Token Analyzer" value={weights.token_analyzer_trust} />
        <WeightBar label="Sentiment" value={weights.sentiment_trust} />
        <WeightBar label="Risk" value={weights.risk_trust} />
        <WeightBar label="Volume" value={weights.volume_weight} />
        <WeightBar label="Whale" value={weights.whale_weight} />
        <WeightBar label="Position Size Mult" value={weights.position_size_mult} />
      </div>

      {/* Learning stats */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-5 space-y-4">
        <h3 className="text-sm font-bold uppercase text-[var(--text-muted)] tracking-wide">Learning Stats</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-[var(--text-muted)]">Learning Rate</p>
            <p className="text-xl font-bold font-mono">{weights.learning_rate?.toFixed(4)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)]">Total Trades</p>
            <p className="text-xl font-bold">{weights.total_trades}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)]">Wins</p>
            <p className="text-xl font-bold text-[var(--green)]">{weights.wins}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)]">Losses</p>
            <p className="text-xl font-bold text-[var(--red)]">{weights.losses}</p>
          </div>
        </div>
        <div className="pt-2 border-t border-[var(--border)]">
          <p className="text-xs text-[var(--text-muted)]">Cumulative P&L</p>
          <p className={`text-2xl font-bold ${weights.total_pnl >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]'}`}>
            {weights.total_pnl >= 0 ? '+' : ''}{weights.total_pnl?.toFixed(4)} SOL
          </p>
        </div>
        <p className="text-xs text-[var(--text-muted)] italic">
          LR decays from 0.30 → 0.02 over 20-trade halflife (EMA)
        </p>
      </div>
    </div>
  )
}
