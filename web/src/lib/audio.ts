/**
 * Shared microphone stream and audio level analyser.
 */

let stream: MediaStream | null = null
let analyser: AnalyserNode | null = null
let ctx: AudioContext | null = null

export async function getMicrophone(): Promise<{ stream: MediaStream; analyser: AnalyserNode }> {
  if (!stream) {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    ctx = new AudioContext()
    const source = ctx.createMediaStreamSource(stream)
    analyser = ctx.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0.7
    source.connect(analyser)
  }
  if (!analyser) throw new Error('Audio analyser not available')
  return { stream, analyser }
}

export function releaseMicrophone() {
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
  analyser = null
  if (ctx?.state !== 'closed') {
    void ctx?.close()
  }
  ctx = null
}

export function getMicLevel(): number {
  if (!analyser) return 0
  const data = new Uint8Array(analyser.frequencyBinCount)
  analyser.getByteFrequencyData(data)
  let sum = 0
  for (let i = 0; i < data.length; i++) sum += data[i]
  return sum / data.length / 255
}
