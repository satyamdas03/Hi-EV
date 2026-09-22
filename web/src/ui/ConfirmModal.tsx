import { useStore } from '../store'
import type { EvBridge } from '../lib/bridge'

export function ConfirmModal({ bridge }: { bridge: EvBridge }) {
  const pending = useStore((s) => s.pendingConfirmation)

  if (!pending) return null

  const handleConfirm = () => {
    useStore.getState().setPendingConfirmation(null)
    bridge.sendConfirmResponse(true)
  }

  const handleDeny = () => {
    useStore.getState().setPendingConfirmation(null)
    bridge.sendConfirmResponse(false)
  }

  return (
    <div className="confirm-overlay">
      <div className="confirm-modal">
        <h3>Confirm action</h3>
        <p className="confirm-prompt">{pending.prompt}</p>
        <div className="confirm-meta">
          <span className="confirm-tier">Tier {pending.tier}</span>
          <span className="confirm-risk">{pending.risk}</span>
        </div>
        <div className="confirm-actions">
          <button className="confirm-deny" onClick={handleDeny}>
            Deny
          </button>
          <button className="confirm-approve" onClick={handleConfirm}>
            Confirm
          </button>
        </div>
        <span className="confirm-hint">
          Or say <kbd>yes</kbd> / <kbd>no</kbd> if listening
        </span>
      </div>
    </div>
  )
}
