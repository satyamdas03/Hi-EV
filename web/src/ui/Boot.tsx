import { useEffect, useState } from 'react'
import { useStore } from '../store'

const LOG = [
  'MOUNT F:/BACKUP/GHOST (HIDDEN)',
  'EXTEND SYSTEM MEMORY .......... OK',
  'TELEMETRY / COMP CLIMATION',
  'REMOVE SYSTEM CONFIGURATION',
  'CHECKSUM ...................... OK',
  'RUN SYSTEM TOOL',
]

export function Boot() {
  const phase = useStore((s) => s.phase)
  const [t, setT] = useState(0)

  useEffect(() => {
    if (phase !== 'boot') {
      setT(0)
      return
    }
    const start = Date.now()
    const id = setInterval(() => setT(Date.now() - start), 50)
    return () => clearInterval(id)
  }, [phase])

  if (phase !== 'boot') return null

  const done = Math.min(1, t / 2600)
  const shown = Math.min(LOG.length, Math.floor(done * LOG.length))

  return (
    <div className="boot">
      <div className="boot-bar">
        <span className="boot-title">INITIATING SYSTEM 1…</span>
        <div className="boot-seg">
          {Array.from({ length: 22 }, (_, i) => (
            <span
              key={i}
              className="boot-seg-cell"
              data-on={i / 22 < done ? '1' : '0'}
            />
          ))}
        </div>
      </div>
      <div className="boot-log">
        {LOG.slice(0, shown).map((l) => (
          <div key={l} className="boot-log-line">
            {l}
          </div>
        ))}
      </div>
      <div className="boot-name">EV</div>
    </div>
  )
}
