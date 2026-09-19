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

export interface EvState {
  phase: Phase
  turns: Turn[]
  caption: string | null
  level: number
  connected: boolean
  error: string | null
  bootNote: string | null
  activeTool: string | null
  isStreaming: boolean
  streamPhase: string | null

  setPhase: (phase: Phase) => void
  addUserTurn: (text: string) => void
  addEvDelta: (text: string) => void
  setCaption: (caption: string | null) => void
  setLevel: (level: number) => void
  setConnected: (connected: boolean) => void
  setError: (error: string | null) => void
  setBootNote: (note: string | null) => void
  setActiveTool: (tool: string | null) => void
  startStream: (phase: string) => void
  stopStream: () => void
  clearError: () => void
}

let idCounter = 0

export const useStore = create<EvState>((set) => ({
  phase: 'offline',
  turns: [],
  caption: null,
  level: 0,
  connected: false,
  error: null,
  bootNote: null,
  activeTool: null,
  isStreaming: false,
  streamPhase: null,

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

  setCaption: (caption) => set({ caption }),
  setLevel: (level) => set({ level }),
  setConnected: (connected) => set({ connected }),
  setError: (error) => set({ error }),
  setBootNote: (note) => set({ bootNote: note }),
  setActiveTool: (tool) => set({ activeTool: tool }),
  clearError: () => set({ error: null }),
}))
