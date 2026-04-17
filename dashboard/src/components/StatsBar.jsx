function Stat({ label, value, color, prefix = '' }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4">
      <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color || 'text-white'}`}>
        {prefix}{typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 4 }) : value}
      </p>
    </div>
  )
}

export default function StatsBar({ stats }) {
  const pnlColor = stats.total_pnl >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]'
  const wrColor = stats.win_rate >= 50 ? 'text-[var(--green)]' : stats.win_rate > 0 ? 'text-[var(--amber)]' : ''

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
      <Stat label="Balance" value={stats.balance} prefix="◎ " />
      <Stat label="Total P&L" value={`${stats.total_pnl >= 0 ? '+' : ''}${stats.total_pnl?.toFixed(4)} SOL`} color={pnlColor} />
      <Stat label="Win Rate" value={`${stats.win_rate?.toFixed(1)}%`} color={wrColor} />
      <Stat label="Trades" value={stats.total_trades} />
      <Stat label="Open" value={stats.open_positions} color="text-[var(--blue)]" />
      <Stat label="Analyzed" value={stats.tokens_analyzed} />
    </div>
  )
}
