import { useState, useEffect, useCallback } from 'react'
import Header from './components/Header'
import StatsBar from './components/StatsBar'
import PositionsTable from './components/PositionsTable'
import ABLog from './components/ABLog'
import WeightsPanel from './components/WeightsPanel'
import ActivityFeed from './components/ActivityFeed'

const API = '/api'

const MOCK = {
  stats: {
    balance: 10.0,
    total_pnl: 0,
    win_rate: 0,
    total_trades: 0,
    open_positions: 0,
    tokens_analyzed: 0,
    uptime: '0m',
    mode: 'DRY_RUN',
  },
  positions: [],
  ab_log: [],
  weights: {
    token_analyzer_trust: 1.0,
    sentiment_trust: 1.0,
    risk_trust: 1.0,
    volume_weight: 1.0,
    whale_weight: 1.0,
    position_size_mult: 1.0,
    learning_rate: 0.30,
    total_trades: 0,
    wins: 0,
    losses: 0,
    total_pnl: 0,
  },
  activity: [],
}

export default function App() {
  const [stats, setStats] = useState(MOCK.stats)
  const [positions, setPositions] = useState(MOCK.positions)
  const [abLog, setAbLog] = useState(MOCK.ab_log)
  const [weights, setWeights] = useState(MOCK.weights)
  const [activity, setActivity] = useState(MOCK.activity)
  const [connected, setConnected] = useState(false)
  const [tab, setTab] = useState('positions')

  const fetchAll = useCallback(async () => {
    try {
      const [s, p, a, w, act] = await Promise.all([
        fetch(`${API}/stats`).then(r => r.json()),
        fetch(`${API}/positions`).then(r => r.json()),
        fetch(`${API}/ab-log`).then(r => r.json()),
        fetch(`${API}/weights`).then(r => r.json()),
        fetch(`${API}/activity`).then(r => r.json()),
      ])
      setStats(s)
      setPositions(p)
      setAbLog(a)
      setWeights(w)
      setActivity(act)
      setConnected(true)
    } catch {
      setConnected(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, 5000)
    return () => clearInterval(id)
  }, [fetchAll])

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <Header connected={connected} mode={stats.mode} />
      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        <StatsBar stats={stats} />

        <div className="flex gap-1 bg-[var(--bg-card)] rounded-lg p-1 w-fit">
          {['positions', 'ab-test', 'weights', 'activity'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer ${
                tab === t
                  ? 'bg-[var(--blue)] text-white'
                  : 'text-[var(--text-muted)] hover:text-white hover:bg-[var(--bg-hover)]'
              }`}
            >
              {t === 'positions' && '📈 Positions'}
              {t === 'ab-test' && '⚖️ A/B Log'}
              {t === 'weights' && '🧠 Weights'}
              {t === 'activity' && '📋 Activity'}
            </button>
          ))}
        </div>

        {tab === 'positions' && <PositionsTable positions={positions} />}
        {tab === 'ab-test' && <ABLog log={abLog} />}
        {tab === 'weights' && <WeightsPanel weights={weights} />}
        {tab === 'activity' && <ActivityFeed activity={activity} />}
      </main>
    </div>
  )
}
