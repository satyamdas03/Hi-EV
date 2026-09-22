import { create } from 'zustand'

export type Phase =
  | 'offline'
  | 'boot'
  | 'dormant'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'streaming'
  | 'tooling'
  | 'error'

export type Turn = {
  id: string
  role: 'user' | 'ev'
  text: string
}

export type Alert = {
  id: string
  category: string
  title: string
  body: string
  items?: unknown[]
  receivedAt: number
}

export type PendingConfirmation = {
  tool: string
  tier: number
  risk: string
  prompt: string
  args: Record<string, unknown>
}

export interface EvState {
  phase: Phase
  turns: Turn[]
  alerts: Alert[]
  caption: string | null
  level: number
  connected: boolean
  error: string | null
  bootNote: string | null
  activeTool: string | null
  isStreaming: boolean
  streamPhase: string | null
  pendingConfirmation: PendingConfirmation | null
  focusRequested: boolean

  setPhase: (phase: Phase) => void
  addUserTurn: (text: string) => void
  addEvDelta: (text: string) => void
  addAlert: (alert: Omit<Alert, 'id' | 'receivedAt'>) => void
  dismissAlert: (id: string) => void
  setCaption: (caption: string | null) => void
  setLevel: (level: number) => void
  setConnected: (connected: boolean) => void
  setError: (error: string | null) => void
  setBootNote: (note: string | null) => void
  setActiveTool: (tool: string | null) => void
  setPendingConfirmation: (confirmation: PendingConfirmation | null) => void
  requestFocus: () => void
  clearFocusRequest: () => void
  startStream: (phase: string) => void
  stopStream: () => void
  clearError: () => void
}

let idCounter = 0

export const useStore = create<EvState>((set) => ({
  phase: 'offline',
  turns: [],
  alerts: [],
  caption: null,
  level: 0,
  connected: false,
  error: null,
  bootNote: null,
  activeTool: null,
  isStreaming: false,
  streamPhase: null,
  pendingConfirmation: null,
  focusRequested: false,

  setPhase: (phase) => set({ phase }),

  startStream: (streamPhase) => set({ isStreaming: true, streamPhase }),

  stopStream: () => set({ isStreaming: false, streamPhase: null }),

  addUserTurn: (text) =>
    set((s) => ({
      turns: [
        ...s.turns,
        { id: String(++idCounter), role: 'user', text },
      ],
    })),

  addEvDelta: (text) =>
    set((s) => {
      const last = s.turns[s.turns.length - 1]
      if (last && last.role === 'ev') {
        return {
          turns: [
            ...s.turns.slice(0, -1),
            { ...last, text: last.text + text },
          ],
        }
      }
      return {
        turns: [
          ...s.turns,
          { id: String(++idCounter), role: 'ev', text },
        ],
      }
    }),

  addAlert: (alert) =>
    set((s) => ({
      alerts: [
        { ...alert, id: String(++idCounter), receivedAt: Date.now() },
        ...s.alerts,
      ],
    })),

  dismissAlert: (id) =>
    set((s) => ({
      alerts: s.alerts.filter((a) => a.id !== id),
    })),

  setCaption: (caption) => set({ caption }),
  setLevel: (level) => set({ level }),
  setConnected: (connected) => set({ connected }),
  setError: (error) => set({ error }),
  setBootNote: (note) => set({ bootNote: note }),
  setActiveTool: (tool) => set({ activeTool: tool }),
  setPendingConfirmation: (pendingConfirmation) => set({ pendingConfirmation }),
  requestFocus: () => set({ focusRequested: true }),
  clearFocusRequest: () => set({ focusRequested: false }),
  clearError: () => set({ error: null }),
}))
