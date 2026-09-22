import { EV_WS_URL } from '../config'

function buildWsUrl(threadId?: string): string {
  if (!threadId) return EV_WS_URL
  const separator = EV_WS_URL.includes('?') ? '&' : '?'
  return `${EV_WS_URL}${separator}thread_id=${encodeURIComponent(threadId)}`
}

export type BridgeMessage =
  | { type: 'transcript'; text: string }
  | { type: 'confirm_response'; confirmed: boolean }
  | { type: 'stop' }
  | { type: 'ping' }

export type BridgeEvent =
  | { type: 'pong' }
  | { type: 'phase'; phase: string }
  | { type: 'delta'; text: string }
  | { type: 'done' }
  | { type: 'error'; message: string }
  | { type: 'alert'; category: string; title: string; body: string; items?: unknown[] }
  | { type: 'confirm'; tool: string; tier: number; risk: string; prompt: string; args: Record<string, unknown> }
  | { type: 'focus' }

/**
 * WebSocket bridge to the Hi-EV daemon.
 *
 * Single connection per browser tab, with auto-reconnect. The daemon is
 * local-only, so this never leaves the machine.
 */
export class EvBridge {
  private ws: WebSocket | null = null
  private reconnectTimer: number | null = null
  private onOpenCb: (() => void) | null = null
  private onCloseCb: (() => void) | null = null
  private onEventCb: ((event: BridgeEvent) => void) | null = null
  private pending: BridgeMessage[] = []

  constructor(private threadId?: string) {}

  setThreadId(threadId: string | undefined) {
    const changed = this.threadId !== threadId
    this.threadId = threadId
    if (changed && this.ws) {
      this.disconnect()
      this.connect()
    }
  }

  connect() {
    if (this.ws) return
    const ws = new WebSocket(buildWsUrl(this.threadId))
    this.ws = ws

    ws.addEventListener('open', () => {
      this.flush()
      this.onOpenCb?.()
    })

    ws.addEventListener('message', (ev) => {
      try {
        const data = JSON.parse(ev.data) as BridgeEvent
        this.onEventCb?.(data)
      } catch {
        // ignore malformed messages
      }
    })

    ws.addEventListener('close', () => {
      this.ws = null
      this.onCloseCb?.()
      this.scheduleReconnect()
    })

    ws.addEventListener('error', () => {
      // let close handler reconnect
      ws.close()
    })
  }

  disconnect() {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
  }

  onOpen(cb: () => void) {
    this.onOpenCb = cb
  }

  onClose(cb: () => void) {
    this.onCloseCb = cb
  }

  onEvent(cb: (event: BridgeEvent) => void) {
    this.onEventCb = cb
  }

  send(msg: BridgeMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    } else {
      this.pending.push(msg)
      this.connect()
    }
  }

  sendTranscript(text: string) {
    this.send({ type: 'transcript', text })
  }

  sendStop() {
    this.send({ type: 'stop' })
  }

  sendConfirmResponse(confirmed: boolean) {
    this.send({ type: 'confirm_response', confirmed })
  }

  private flush() {
    while (this.pending.length) {
      const msg = this.pending.shift()
      if (msg) this.send(msg)
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer !== null) return
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, 2000)
  }
}
