/**
 * Browser-native TTS queue with sentence-level chunking.
 */

const queue: SpeechSynthesisUtterance[] = []
let speaking = false

function next() {
  if (!queue.length) {
    speaking = false
    return
  }
  speaking = true
  const u = queue.shift()!
  u.onend = () => next()
  u.onerror = () => next()
  window.speechSynthesis.speak(u)
}

export function speak(text: string) {
  // Split into sentences so longer answers don't block barge-in for too long.
  const chunks = text.match(/[^.!?]+[.!?]+|\S+/g) || [text]
  for (const chunk of chunks) {
    const u = new SpeechSynthesisUtterance(chunk.trim())
    u.rate = 1.05
    u.pitch = 0.95
    queue.push(u)
  }
  if (!speaking) next()
}

export function stopSpeaking() {
  window.speechSynthesis.cancel()
  queue.length = 0
  speaking = false
}

export function isSpeaking(): boolean {
  return speaking || window.speechSynthesis.speaking
}
