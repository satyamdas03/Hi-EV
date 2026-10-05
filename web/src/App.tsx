import { useEffect, useRef } from 'react'
import { EvBridge } from './lib/bridge'
import { getMicLevel } from './lib/audio'
import { startListening, stopListening, handleBridgeEvent, startWakeListening, stopWakeListening } from './lib/voice'
import { onShortcutTriggered } from './lib/tauri'
import { useStore } from './store'
import { EV_API_URL } from './config'
import { Scene } from './scene/Scene'
import { Boot } from './ui/Boot'
import { Diagnostics } from './ui/Diagnostics'
import { Hud } from './ui/Hud'
import { Ignition } from './ui/Ignition'
import { SetupWizard } from './ui/SetupWizard'
import { Suggestions } from './ui/Suggestions'

export function App() {
  const bridge = useRef(new EvBridge()).current
  const booted = useRef(false)
  const setPhase = useStore((s) => s.setPhase)
  const setConnected = useStore((s) => s.setConnected)
  const setLevel = useStore((s) => s.setLevel)
  const setError = useStore((s) => s.setError)
  const focusRequested = useStore((s) => s.focusRequested)
  const clearFocusRequest = useStore((s) => s.clearFocusRequest)
  const setupNeeded = useStore((s) => s.setupNeeded)
  const setSetupNeeded = useStore((s) => s.setSetupNeeded)

  useEffect(() => {
    if (!focusRequested) return
    clearFocusRequest()
    window.focus()
    const phase = useStore.getState().phase
    if (phase === 'dormant' || phase === 'speaking' || phase === 'thinking') {
      void startListening(bridge)
    }
  }, [focusRequested, clearFocusRequest, bridge])

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
    fetch(`${EV_API_URL}/setup`)
      .then((res) => {
        if (!res.ok) throw new Error(`setup check failed (${res.status})`)
        return res.json()
      })
      .then((data) => {
        setSetupNeeded(Boolean(data.needs_setup))
      })
      .catch(() => {
        // If the daemon is not reachable, assume we are still booting and do not block UI.
        setSetupNeeded(false)
      })
  }, [setSetupNeeded])

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
    const unsubscribe = useStore.subscribe((state) => {
      if (state.phase === 'dormant') {
        startWakeListening(bridge)
      } else {
        stopWakeListening()
      }
    })
    // Prime it once with the current phase.
    if (useStore.getState().phase === 'dormant') {
      startWakeListening(bridge)
    }
    return () => {
      unsubscribe()
      stopWakeListening()
    }
  }, [bridge])

  useEffect(() => {
    const cleanup = onShortcutTriggered(() => {
      window.focus()
      const phase = useStore.getState().phase
      if (phase === 'offline') {
        // Fall through to wake listening after bridge connects.
      } else if (phase === 'dormant' || phase === 'speaking' || phase === 'thinking') {
        void startListening(bridge)
      }
    })
    return cleanup
  }, [bridge])

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
      {setupNeeded ? (
        <SetupWizard />
      ) : (
        <>
          <Ignition onStart={powerOn} />
          <Boot />
          <Hud bridge={bridge} />
          <Suggestions />
          <Diagnostics />
        </>
      )}
    </>
  )
}
