import { useEffect, useState } from 'react'
import { EV_API_URL } from '../config'
import type { EvBridge } from '../lib/bridge'

type Thread = {
  id: string
  title: string | null
  updated_at: string | null
}

export function Threads({ bridge }: { bridge: EvBridge }) {
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeId, setActiveId] = useState<string | undefined>(bridge['threadId'])
  const [loading, setLoading] = useState(true)

  const fetchThreads = async () => {
    try {
      const res = await fetch(`${EV_API_URL}/threads`)
      const data = (await res.json()) as Thread[]
      setThreads(data)
    } catch {
      // ignore in silent/local-first mode
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchThreads()
    const id = setInterval(fetchThreads, 5000)
    return () => clearInterval(id)
  }, [])

  const createThread = async () => {
    try {
      const res = await fetch(`${EV_API_URL}/threads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New thread' }),
      })
      const thread = (await res.json()) as Thread
      setThreads((prev) => [thread, ...prev])
      selectThread(thread.id)
    } catch {
      // ignore
    }
  }

  const selectThread = (id: string) => {
    setActiveId(id)
    bridge.setThreadId(id)
  }

  return (
    <div className="threads">
      <div className="threads-head">
        <span className="threads-title">THREADS</span>
        <button className="threads-new" onClick={createThread} aria-label="New thread">
          +
        </button>
      </div>
      {loading && threads.length === 0 && (
        <div className="threads-empty">Loading…</div>
      )}
      <div className="threads-list">
        {threads.map((t) => (
          <button
            key={t.id}
            className={`thread-row ${t.id === activeId ? 'thread-active' : ''}`}
            onClick={() => selectThread(t.id)}
          >
            <span className="thread-title">{t.title || 'Untitled thread'}</span>
            <span className="thread-time">{formatTime(t.updated_at)}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

function formatTime(iso: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}
