import { useEffect, useState } from 'react'
import { useStore } from '../store'

export function Diagnostics() {
  const [open, setOpen] = useState(false)
  const phase = useStore((s) => s.phase)
  const connected = useStore((s) => s.connected)
  const level = useStore((s) => s.level)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (e.key === 'd' && !e.repeat && !e.metaKey && !e.ctrlKey && !e.altKey) {
        setOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (!open) return null

  const sr = 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window
  const synth = 'speechSynthesis' in window

  return (
    <div className="diag">
      <div className="diag-head">DIAGNOSTICS · D to close</div>
      <div className="diag-row">
        <span className="diag-k">connection</span>
        <span className={connected ? 'diag-v diag-ok' : 'diag-v diag-bad'}>
          {connected ? 'connected' : 'disconnected'}
        </span>
      </div>
      <div className="diag-row">
        <span className="diag-k">phase</span>
        <span className="diag-v">{phase}</span>
      </div>
      <div className="diag-row">
        <span className="diag-k">mic level</span>
        <span className="diag-v">{(level * 100).toFixed(0)}%</span>
      </div>
      <div className="diag-row">
        <span className="diag-k">speech recogniser</span>
        <span className={sr ? 'diag-v diag-ok' : 'diag-v diag-bad'}>{sr ? 'available' : 'unavailable'}</span>
      </div>
      <div className="diag-row">
        <span className="diag-k">speech synthesis</span>
        <span className={synth ? 'diag-v diag-ok' : 'diag-v diag-bad'}>{synth ? 'available' : 'unavailable'}</span>
      </div>
    </div>
  )
}
