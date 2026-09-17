import { useStore } from '../store'

export function Ignition({ onStart }: { onStart: () => void }) {
  const phase = useStore((s) => s.phase)
  if (phase !== 'offline') return null

  return (
    <button className="ignition" onClick={onStart}>
      <span className="ignition-ring" />
      <span className="ignition-label">
        <span className="ignition-word">INITIALISE</span>
        <span className="ignition-sub">click, or press Space, to power up</span>
      </span>
    </button>
  )
}
