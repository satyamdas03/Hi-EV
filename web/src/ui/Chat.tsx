import { useEffect, useRef } from 'react'
import { useStore } from '../store'
import type { EvBridge } from '../lib/bridge'

export function Chat({ bridge }: { bridge: EvBridge }) {
  const turns = useStore((s) => s.turns)
  const isStreaming = useStore((s) => s.isStreaming)
  const streamPhase = useStore((s) => s.streamPhase)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [turns.length, isStreaming])

  const handleStop = () => {
    bridge.sendStop()
  }

  const formatPhase = (phase: string | null) => {
    if (!phase) return null
    if (phase === 'streaming') return 'STREAMING'
    if (phase.startsWith('route:')) return `ROUTE ${phase.slice(6).toUpperCase()}`
    return phase.toUpperCase()
  }

  return (
    <div className="chat">
      <div className="chat-scroll" ref={scrollRef}>
        {turns.map((turn, i) => {
          const isLast = i === turns.length - 1
          const streamingHere = isLast && turn.role === 'ev' && isStreaming
          return (
            <div key={turn.id} className={`chat-bubble chat-bubble-${turn.role}`}>
              <span className="chat-who">{turn.role === 'user' ? 'YOU' : 'EV'}</span>
              <span className="chat-text">
                {turn.text}
                {streamingHere && <span className="stream-caret" aria-hidden="true" />}
              </span>
            </div>
          )
        })}
      </div>
      {isStreaming && (
        <div className="chat-controls">
          <span className="phase-badge">{formatPhase(streamPhase)}</span>
          <button className="stop-btn" onClick={handleStop} aria-label="Stop generation">
            <span className="stop-icon" aria-hidden="true" />
            STOP
          </button>
        </div>
      )}
    </div>
  )
}
