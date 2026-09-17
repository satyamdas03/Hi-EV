import { useEffect, useState } from 'react'
import { useStore } from '../store'

const EXAMPLES = [
  'status of Hi-EV',
  'what are my alerts',
  'what deadlines do I have',
  'brief me',
  'research best local voice stack',
]

const ROTATE_MS = 5000

export function Suggestions() {
  const phase = useStore((s) => s.phase)
  const turns = useStore((s) => s.turns)
  const [i, setI] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % EXAMPLES.length), ROTATE_MS)
    return () => clearInterval(id)
  }, [])

  if (phase !== 'dormant' || turns.length > 0) return null

  return (
    <div className="suggest">
      <span className="suggest-lead">try:</span>
      <span className="suggest-text">
        “{EXAMPLES[i]}”
      </span>
    </div>
  )
}
