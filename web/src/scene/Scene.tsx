import { Canvas, useFrame } from '@react-three/fiber'
import { EffectComposer, Bloom, Vignette, Noise } from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'
import { useMemo } from 'react'
import * as THREE from 'three'
import { useStore, type Phase } from '../store'
import { Core } from './Core'
import { Particles } from './Particles'

const spinFor: Record<Phase, number> = {
  offline: 0.05,
  boot: 2.8,
  dormant: 0.25,
  listening: 1.1,
  thinking: 2.6,
  speaking: 1.3,
  streaming: 2.2,
  tooling: 3.0,
  error: 0.4,
}

export type Drive = {
  color: THREE.Color
  level: number
  spin: number
  open: number
}

function Rig() {
  const drive = useMemo<Drive>(
    () => ({
      color: new THREE.Color('#19c4c4'),
      level: 0,
      spin: spinFor.offline,
      open: 0,
    }),
    [],
  )

  useFrame((state, dt) => {
    const { phase, level } = useStore.getState()
    const phaseColors: Record<Phase, string> = {
      offline: '#19c4c4',
      boot: '#19c4c4',
      dormant: '#19c4c4',
      listening: '#00e5ff',
      thinking: '#ff9f43',
      speaking: '#19c4c4',
      streaming: '#c9fdff',
      tooling: '#ff9f43',
      error: '#ff4d4d',
    }
    drive.color.lerp(new THREE.Color(phaseColors[phase]), Math.min(1, dt * 2.5))
    drive.spin += (spinFor[phase] - drive.spin) * Math.min(1, dt * 2)
    drive.open = phase === 'offline' ? 0 : phase === 'boot' ? 0.7 : 1
    drive.level += (Math.max(level, phase === 'dormant' ? 0.03 : 0.1) - drive.level) * Math.min(1, dt * 8)

    const t = state.clock.elapsedTime
    state.camera.position.x = Math.sin(t * 0.1) * 0.2
    state.camera.position.y = Math.cos(t * 0.13) * 0.15
    state.camera.lookAt(0, 0, 0)
  })

  return (
    <>
      <Core drive={drive} />
      <Particles drive={drive} />
    </>
  )
}

export function Scene() {
  return (
    <Canvas
      className="scene"
      camera={{ position: [0, 0, 6.2], fov: 45 }}
      gl={{ antialias: true, alpha: true }}
      dpr={[1, 2]}
    >
      <Rig />
      <EffectComposer multisampling={0}>
        <Bloom intensity={1.2} luminanceThreshold={0.25} luminanceSmoothing={0.85} mipmapBlur radius={0.7} />
        <Noise opacity={0.04} blendFunction={BlendFunction.OVERLAY} />
        <Vignette offset={0.25} darkness={0.9} />
      </EffectComposer>
    </Canvas>
  )
}
