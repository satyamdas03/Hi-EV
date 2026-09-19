import { useEffect, useRef } from 'react'
import { EvBridge } from './lib/bridge'
import { getMicLevel } from './lib/audio'
import { startListening, stopListening, handleBridgeEvent } from './lib/voice'
import { useStore } from './store'
import { Scene } from './scene/Scene'
import { Boot } from './ui/Boot'
import { Diagnostics } from './ui/Diagnostics'
import { Hud } from './ui/Hud'
import { Ignition } from './ui/Ignition'
import { Suggestions } from './ui/Suggestions'

export function App() {
  const bridge = useRef(new EvBridge()).current
  const booted = useRef(false)
  const setPhase = useStore((s) => s.setPhase)
  const setConnected = useStore((s) => s.setConnected)
  const setLevel = useStore((s) => s.setLevel)
  const setError = useStore((s) => s.setError)

  useEffect(() => {
    let raf = 0
    const tick = () => {
      raf = requestAnimationFrame(tick)
      setLevel(getMicLevel())
    }
    tick()
    return () => cancelAnimationFrame(raf)
  }, [setLevel])

  useEffect(() => {
    bridge.onOpen(() => setConnected(true))
    bridge.onClose(() => setConnected(false))
    bridge.onEvent((event) => {
      if (event.type === 'error') {
        setError(event.message)
        return
      }
      setError(null)
      handleBridgeEvent(event)
    })
    bridge.connect()
    return () => bridge.disconnect()
  }, [bridge, setConnected, setError])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (e.repeat) return
      if (e.code === 'Space' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault()
        const phase = useStore.getState().phase
        if (phase === 'offline') {
          powerOn()
        } else if (phase === 'dormant' || phase === 'speaking' || phase === 'thinking') {
          void startListening(bridge)
        } else if (phase === 'listening') {
          stopListening()
        }
      }
    }

    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        const phase = useStore.getState().phase
        if (phase === 'listening') {
          stopListening()
        }
      }
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [bridge])

  const powerOn = () => {
    if (booted.current) return
    booted.current = true
    setPhase('boot')
    window.setTimeout(() => {
      setPhase('dormant')
    }, 3000)
  }

  return (
    <>
      <Scene />
      <Ignition onStart={powerOn} />
      <Boot />
      <Hud bridge={bridge} />
      <Suggestions />
      <Diagnostics />
    </>
  )
}
