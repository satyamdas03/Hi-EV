/**
 * Minimal energy-based voice-activity detector.
 *
 * Not a production VAD, but enough to know when the user is speaking while
 * the push-to-talk key is held, and to decide when a SpeechRecognition result
 * is final.
 */

import { getMicLevel } from './audio'

const SPEECH_THRESHOLD = 0.08
const SILENCE_MS = 1200

export type VADState = 'silent' | 'speaking'

let state: VADState = 'silent'
let lastSpeechAt = 0
let raf = 0
let callback: ((state: VADState) => void) | null = null

function tick() {
  raf = requestAnimationFrame(tick)
  const level = getMicLevel()
  const now = performance.now()

  if (level > SPEECH_THRESHOLD) {
    state = 'speaking'
    lastSpeechAt = now
    callback?.('speaking')
  } else if (state === 'speaking' && now - lastSpeechAt > SILENCE_MS) {
    state = 'silent'
    callback?.('silent')
  }
}

export function startVAD(cb: (state: VADState) => void) {
  stopVAD()
  callback = cb
  tick()
}

export function stopVAD() {
  if (raf) cancelAnimationFrame(raf)
  raf = 0
  state = 'silent'
  callback = null
}

export function currentVADState(): VADState {
  return state
}
