export default function Header({ connected, mode }) {
  return (
    <header className="border-b border-[var(--border)] bg-[var(--bg-card)]">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold tracking-tight">
            ⚡ NEXUS<span className="text-[var(--blue)]"> AI</span>
          </span>
          <span className="text-xs bg-[var(--bg-hover)] text-[var(--text-muted)] px-2 py-0.5 rounded">
            {mode}
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? 'bg-[var(--green)] animate-pulse-dot' : 'bg-[var(--red)]'
            }`}
          />
          <span className="text-[var(--text-muted)]">
            {connected ? 'Bot connected' : 'Bot offline'}
          </span>
        </div>
      </div>
    </header>
  )
}
