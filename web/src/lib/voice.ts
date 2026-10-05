/**
 * Voice loop for the Hi-EV web face.
 *
 * Uses the browser's built-in SpeechRecognition (where available) for STT and
 * the Web Speech API for TTS. This is the fastest path to a working voice
 * interface; local Whisper/Piper/Kokoro can replace it later.
 */

import { EV_API_URL } from '../config'
import { useStore } from '../store'
import type { BridgeEvent } from './bridge'
import { EvBridge } from './bridge'
import { getMicrophone, releaseMicrophone } from './audio'
import { IS_TAURI } from './tauri'
import { isSpeaking, speak, stopSpeaking } from './tts'

let recognition: SpeechRecognition | null = null
let wakeRecognition: SpeechRecognition | null = null
let active = false
let wakeActive = false

const WAKE_PHRASE = (import.meta.env.VITE_EV_WAKE_PHRASE ?? 'hey ev').toLowerCase()
const WAKE_ENABLED = import.meta.env.VITE_EV_WAKE_ENABLED === 'true' || !import.meta.env.VITE_EV_WAKE_ENABLED

function getSpeechRecognition(): SpeechRecognition | null {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) return null
  return new SR()
}

function setPhase(phase: ReturnType<typeof useStore.getState>['phase']) {
  useStore.getState().setPhase(phase)
}

async function recordWithMediaRecorder(maxMs = 5000): Promise<Blob> {
  const { stream } = await getMicrophone()
  const mimeType = MediaRecorder.isTypeSupported('audio/wav')
    ? 'audio/wav'
    : MediaRecorder.isTypeSupported('audio/webm')
      ? 'audio/webm'
      : MediaRecorder.isTypeSupported('audio/mp4')
        ? 'audio/mp4'
        : ''
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
  const chunks: Blob[] = []
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data)
  }
  recorder.start(250)
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      if (recorder.state !== 'inactive') recorder.stop()
    }, maxMs)
    recorder.onstop = () => {
      window.clearTimeout(timer)
      const blob = new Blob(chunks, { type: mimeType || 'audio/wav' })
      resolve(blob)
    }
    recorder.onerror = (e) => {
      window.clearTimeout(timer)
      reject(new Error(`Recorder error: ${e}`))
    }
  })
}

async function transcribeBlob(blob: Blob): Promise<string> {
  const formData = new FormData()
  const ext = blob.type === 'audio/webm' ? 'webm' : blob.type === 'audio/mp4' ? 'mp4' : 'wav'
  formData.append('audio', blob, `voice.${ext}`)
  const res = await fetch(`${EV_API_URL}/voice/transcribe`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'Transcription request failed' }))
    throw new Error(body.detail || `Transcription failed (${res.status})`)
  }
  const data = (await res.json()) as { transcript?: string }
  return data.transcript || ''
}

async function startDaemonListening(bridge: EvBridge) {
  try {
    setPhase('listening')
    stopSpeaking()
    const blob = await recordWithMediaRecorder(5000)
    const text = await transcribeBlob(blob)
    releaseMicrophone()
    if (text.trim()) {
      useStore.getState().setCaption(null)
      useStore.getState().addUserTurn(text.trim())
      setPhase('thinking')
      bridge.sendTranscript(text.trim())
    } else {
      setPhase('dormant')
    }
  } catch (err) {
    releaseMicrophone()
    useStore.getState().setError(`Voice fallback failed: ${err}`)
    setPhase('dormant')
  }
}

export async function startListening(bridge: EvBridge) {
  if (active) return
  active = true

  setPhase('listening')
  stopSpeaking()

  // Hold the mic so the analyser starts and the HUD level meter wakes up.
  try {
    await getMicrophone()
  } catch (err) {
    useStore.getState().setError(`Microphone unavailable: ${err}`)
    setPhase('dormant')
    active = false
    return
  }

  const rec = getSpeechRecognition()
  if (!rec) {
    // Inside the Tauri desktop shell, fall back to the local daemon's
    // /voice/transcribe endpoint instead of relying on browser APIs.
    if (IS_TAURI) {
      active = false
      await startDaemonListening(bridge)
      return
    }
    useStore.getState().setError('SpeechRecognition not supported in this browser.')
    setPhase('dormant')
    active = false
    return
  }

  recognition = rec
  recognition.continuous = false
  recognition.interimResults = true
  recognition.lang = 'en-US'

  let finalText = ''
  let sent = false

  recognition.onresult = (event: SpeechRecognitionEvent) => {
    let interim = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i]
      if (result.isFinal) {
        finalText += result[0].transcript
      } else {
        interim += result[0].transcript
      }
    }
    useStore.getState().setCaption(interim || finalText || '...')

    // Voice confirmation / denial while a T2 confirmation is pending.
    const pending = useStore.getState().pendingConfirmation
    if (pending) {
      const text = (interim + finalText).trim().toLowerCase()
      if (/^(yes|yeah|yep|confirm|go ahead|do it|ok|okay)(\s|$)/.test(text)) {
        sent = true
        bridge.sendConfirmResponse(true)
        useStore.getState().setPendingConfirmation(null)
        cleanup()
        return
      }
      if (/^(no|nope|cancel|deny|abort|stop|don't)(\s|$)/.test(text)) {
        sent = true
        bridge.sendConfirmResponse(false)
        useStore.getState().setPendingConfirmation(null)
        cleanup()
        return
      }
    }
  }

  recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
    if (event.error === 'aborted') return
    useStore.getState().setError(`Speech error: ${event.error}`)
    cleanup()
  }

  recognition.onend = () => {
    if (!active || sent) return
    if (finalText.trim()) {
      sent = true
      useStore.getState().setCaption(null)
      useStore.getState().addUserTurn(finalText.trim())
      setPhase('thinking')
      bridge.sendTranscript(finalText.trim())
    } else {
      setPhase('dormant')
    }
    cleanup()
  }

  try {
    recognition.start()
  } catch {
    cleanup()
  }
}

export function stopListening() {
  recognition?.stop()
  active = false
}

function cleanup() {
  active = false
  recognition = null
  releaseMicrophone()
}

export function startWakeListening(bridge: EvBridge) {
  if (wakeActive) return
  if (!WAKE_ENABLED) return
  const SR = getSpeechRecognition()
  if (!SR) return

  wakeActive = true
  wakeRecognition = SR
  wakeRecognition.continuous = true
  wakeRecognition.interimResults = true
  wakeRecognition.lang = 'en-US'

  let lastText = ''

  wakeRecognition.onresult = (event: SpeechRecognitionEvent) => {
    let text = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      text += event.results[i][0].transcript
    }
    lastText = text.toLowerCase()
    if (lastText.includes(WAKE_PHRASE)) {
      stopWakeListening()
      void startListening(bridge)
    }
  }

  wakeRecognition.onerror = () => {
    // Continuous wake listening is best-effort; restart on errors.
    stopWakeListening()
  }

  wakeRecognition.onend = () => {
    wakeActive = false
    wakeRecognition = null
    // Restart if we are still dormant and no one has taken the mic.
    const phase = useStore.getState().phase
    if (phase === 'dormant' && !active) {
      setTimeout(() => startWakeListening(bridge), 500)
    }
  }

  try {
    wakeRecognition.start()
  } catch {
    stopWakeListening()
  }
}

export function stopWakeListening() {
  wakeRecognition?.stop()
  wakeActive = false
  wakeRecognition = null
}

export function handleBridgeEvent(event: BridgeEvent) {
  const state = useStore.getState()
  if (event.type === 'phase') {
    const raw = event.phase
    if (raw === 'streaming' || raw.startsWith('route:')) {
      state.startStream(raw)
      if (raw === 'streaming') setPhase('streaming')
    } else {
      if (state.isStreaming) state.stopStream()
      setPhase(raw as ReturnType<typeof useStore.getState>['phase'])
    }
  } else if (event.type === 'delta' && event.text) {
    if (state.isStreaming) {
      state.addEvDelta(event.text)
    } else {
      setPhase('speaking')
      state.addEvDelta(event.text)
      speak(event.text)
    }
  } else if (event.type === 'done') {
    if (state.isStreaming) {
      state.stopStream()
      const lastEv = [...state.turns].reverse().find((t) => t.role === 'ev')
      if (lastEv?.text) speak(lastEv.text)
    }
    state.setPendingConfirmation(null)
    if (!isSpeaking()) setPhase('dormant')
  } else if (event.type === 'error') {
    state.setError(event.message)
    state.stopStream()
    state.setPendingConfirmation(null)
    setPhase('dormant')
  } else if (event.type === 'alert') {
    state.addAlert({
      category: event.category,
      title: event.title,
      body: event.body,
      items: event.items,
    })
  } else if (event.type === 'confirm') {
    state.setPendingConfirmation({
      tool: event.tool,
      tier: event.tier,
      risk: event.risk,
      prompt: event.prompt,
      args: event.args,
    })
    setPhase('tooling')
  } else if (event.type === 'focus') {
    state.requestFocus()
  }
}
