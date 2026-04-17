export default function PositionsTable({ positions }) {
  if (!positions.length) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-12 text-center">
        <p className="text-4xl mb-3">📈</p>
        <p className="text-[var(--text-muted)]">No open positions</p>
        <p className="text-xs text-[var(--text-muted)] mt-1">Positions will appear here when the bot enters trades</p>
      </div>
    )
  }

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] text-[var(--text-muted)] text-xs uppercase">
            <th className="text-left p-3">Token</th>
            <th className="text-right p-3">Entry</th>
            <th className="text-right p-3">Current</th>
            <th className="text-right p-3">P&L %</th>
            <th className="text-right p-3">Size (SOL)</th>
            <th className="text-right p-3">Age</th>
            <th className="text-center p-3">SL / TP</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p, i) => {
            const pnl = p.pnl_percent ?? 0
            const pnlColor = pnl >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]'
            return (
              <tr key={i} className="border-b border-[var(--border)] hover:bg-[var(--bg-hover)] transition-colors">
                <td className="p-3 font-medium">{p.symbol || p.token?.slice(0, 8)}</td>
                <td className="p-3 text-right font-mono text-xs">${p.entry_price?.toFixed(10)}</td>
                <td className="p-3 text-right font-mono text-xs">${p.current_price?.toFixed(10)}</td>
                <td className={`p-3 text-right font-bold ${pnlColor}`}>
                  {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
                </td>
                <td className="p-3 text-right">{p.size_sol?.toFixed(3)}</td>
                <td className="p-3 text-right text-[var(--text-muted)]">{p.age || '—'}</td>
                <td className="p-3 text-center text-xs text-[var(--text-muted)]">
                  <span className="text-[var(--red)]">-{p.stop_loss ?? 20}%</span>
                  {' / '}
                  <span className="text-[var(--green)]">+{p.take_profit ?? 40}%</span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
