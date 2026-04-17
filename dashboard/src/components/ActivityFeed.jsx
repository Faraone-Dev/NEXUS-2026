export default function ActivityFeed({ activity }) {
  if (!activity.length) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-12 text-center">
        <p className="text-4xl mb-3">📋</p>
        <p className="text-[var(--text-muted)]">No activity yet</p>
        <p className="text-xs text-[var(--text-muted)] mt-1">Bot scan events, trades, and alerts will show here</p>
      </div>
    )
  }

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg divide-y divide-[var(--border)] max-h-[600px] overflow-y-auto">
      {activity.slice(-100).reverse().map((event, i) => (
        <div key={i} className="p-3 flex items-start gap-3 hover:bg-[var(--bg-hover)] transition-colors">
          <span className="text-lg flex-shrink-0">
            {event.type === 'buy' && '🟢'}
            {event.type === 'sell' && '🔴'}
            {event.type === 'skip' && '⏭️'}
            {event.type === 'alert' && '🔔'}
            {event.type === 'scan' && '🔍'}
            {!['buy', 'sell', 'skip', 'alert', 'scan'].includes(event.type) && '📌'}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm">{event.message}</p>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">{event.timestamp}</p>
          </div>
          {event.pnl !== undefined && (
            <span className={`text-sm font-bold flex-shrink-0 ${
              event.pnl >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]'
            }`}>
              {event.pnl >= 0 ? '+' : ''}{event.pnl.toFixed(2)}%
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
