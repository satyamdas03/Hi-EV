import { useStore } from '../store'

export function Alerts() {
  const alerts = useStore((s) => s.alerts)
  const dismissAlert = useStore((s) => s.dismissAlert)

  if (!alerts.length) return null

  return (
    <div className="alerts">
      {alerts.slice(0, 3).map((alert) => (
        <div key={alert.id} className={`alert alert-${alert.category}`}>
          <div className="alert-head">
            <span className="alert-title">{alert.title}</span>
            <button
              className="alert-dismiss"
              onClick={() => dismissAlert(alert.id)}
              aria-label="Dismiss alert"
            >
              ×
            </button>
          </div>
          <div className="alert-body">{alert.body}</div>
        </div>
      ))}
    </div>
  )
}
