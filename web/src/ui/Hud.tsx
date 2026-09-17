import { useStore, type Phase } from '../store'

const statusText: Record<Phase, string> = {
  offline: 'OFFLINE',
  boot: 'INITIALISING',
  dormant: 'STANDBY — PRESS SPACE',
  listening: 'LISTENING',
  thinking: 'PROCESSING',
  speaking: 'RESPONDING',
  tooling: 'ACCESSING SYSTEMS',
  error: 'ERROR',
}

export function Hud() {
  const phase = useStore((s) => s.phase)
  const turns = useStore((s) => s.turns)
  const caption = useStore((s) => s.caption)
  const level = useStore((s) => s.level)
  const connected = useStore((s) => s.connected)
  const error = useStore((s) => s.error)
  const activeTool = useStore((s) => s.activeTool)

  return (
    <div className="hud">
      <header className="hud-top">
        <div className="brand">
          <span className="brand-mark">EV</span>
          <span className="brand-sub">Personal AI Operating System</span>
        </div>
        <div className="status">
          <span className={`dot ${connected ? 'dot-on' : 'dot-off'}`} />
          <span className="status-text">{statusText[phase]}</span>
        </div>
      </header>

      <aside className="rail rail-right">
        <div className="rail-title">SIGNAL</div>
        <div className="meter">
          <div className="meter-fill" style={{ height: `${level * 100}%` }} />
        </div>
      </aside>

      {activeTool && (
        <div className="tool-badge">
          <span className="spinner" />
          <span className="tool-name">{activeTool}</span>
        </div>
      )}

      <div className="log">
        {turns.slice(-6).map((t) => (
          <div key={t.id} className={`log-line log-${t.role}`}>
            <span className="log-who">{t.role === 'user' ? 'YOU' : 'EV'}</span>
            <span className="log-text">{t.text}</span>
          </div>
        ))}
      </div>

      {caption && (
        <div className="caption">{caption}</div>
      )}

      {error && (
        <div className="error-bar">{error}</div>
      )}

      <footer className="hud-bottom">
        <span className="hint">
          press <kbd>Space</kbd> to talk · <kbd>D</kbd> diagnostics
        </span>
      </footer>
    </div>
  )
}
