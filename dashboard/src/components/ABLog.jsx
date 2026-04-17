export default function ABLog({ log }) {
  if (!log.length) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-12 text-center">
        <p className="text-4xl mb-3">⚖️</p>
        <p className="text-[var(--text-muted)]">No A/B comparisons yet</p>
        <p className="text-xs text-[var(--text-muted)] mt-1">
          Each token analysis compares DeepSeek LLM vs rule-based scorer
        </p>
      </div>
    )
  }

  const agrees = log.filter(l => l.agree).length
  const total = log.length
  const agreeRate = total > 0 ? ((agrees / total) * 100).toFixed(1) : 0

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4 flex items-center gap-6">
        <div>
          <span className="text-xs text-[var(--text-muted)] uppercase">Agreement Rate</span>
          <p className="text-2xl font-bold text-[var(--blue)]">{agreeRate}%</p>
        </div>
        <div>
          <span className="text-xs text-[var(--text-muted)] uppercase">Total Comparisons</span>
          <p className="text-2xl font-bold">{total}</p>
        </div>
        <div>
          <span className="text-xs text-[var(--text-muted)] uppercase">Disagree</span>
          <p className="text-2xl font-bold text-[var(--amber)]">{total - agrees}</p>
        </div>
      </div>

      {/* Log table */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-[var(--text-muted)] text-xs uppercase">
              <th className="text-left p-3">Token</th>
              <th className="text-center p-3">LLM</th>
              <th className="text-center p-3">Rule</th>
              <th className="text-center p-3">Match</th>
              <th className="text-right p-3">Rule Score</th>
              <th className="text-left p-3">Reasons</th>
            </tr>
          </thead>
          <tbody>
            {log.slice(-50).reverse().map((entry, i) => (
              <tr key={i} className="border-b border-[var(--border)] hover:bg-[var(--bg-hover)] transition-colors">
                <td className="p-3 font-medium">{entry.symbol}</td>
                <td className="p-3 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                    entry.llm_decision === 'BUY' ? 'bg-green-900/40 text-[var(--green)]' : 'bg-red-900/40 text-[var(--red)]'
                  }`}>
                    {entry.llm_decision}
                  </span>
                </td>
                <td className="p-3 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                    entry.rule_decision === 'BUY' ? 'bg-green-900/40 text-[var(--green)]' : 'bg-red-900/40 text-[var(--red)]'
                  }`}>
                    {entry.rule_decision}
                  </span>
                </td>
                <td className="p-3 text-center">
                  {entry.agree
                    ? <span className="text-[var(--green)]">✓</span>
                    : <span className="text-[var(--amber)]">✗</span>
                  }
                </td>
                <td className="p-3 text-right font-mono">{entry.rule_score}/100</td>
                <td className="p-3 text-xs text-[var(--text-muted)] max-w-xs truncate">
                  {entry.reasons || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
