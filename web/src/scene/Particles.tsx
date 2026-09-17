import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { Drive } from './Scene'

const COUNT = 3000

const vertexShader = `
  uniform float uTime;
  uniform float uLevel;
  attribute float aSeed;
  attribute float aRadius;
  varying float vAlpha;

  void main() {
    float t = uTime * (0.05 + aSeed * 0.04);
    float c = cos(t), s = sin(t);
    vec3 p = vec3(position.x * c - position.z * s, position.y, position.x * s + position.z * c);
    p *= 1.0 + uLevel * 0.25;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    vAlpha = smoothstep(-10.0, -2.0, mv.z) * (0.25 + uLevel * 0.35) * (1.0 - aRadius * 0.5);
    gl_PointSize = 3.0 * (1.0 + uLevel * 0.6) * (10.0 / -mv.z);
  }
`

const fragmentShader = `
  uniform vec3 uColor;
  varying float vAlpha;
  void main() {
    vec2 d = gl_PointCoord - 0.5;
    if (length(d) > 0.5) discard;
    gl_FragColor = vec4(uColor, vAlpha);
  }
`

export function Particles({ drive }: { drive: Drive }) {
  const mat = useRef<THREE.ShaderMaterial>(null)

  const { positions, seeds, radii } = useMemo(() => {
    const positions = new Float32Array(COUNT * 3)
    const seeds = new Float32Array(COUNT)
    const radii = new Float32Array(COUNT)
    for (let i = 0; i < COUNT; i++) {
      const u = Math.random() * 2 - 1
      const theta = Math.random() * Math.PI * 2
      const r = Math.sqrt(1 - u * u)
      const radius = 1.9 + Math.pow(Math.random(), 2) * 2.2
      positions[i * 3] = Math.cos(theta) * r * radius
      positions[i * 3 + 1] = u * radius
      positions[i * 3 + 2] = Math.sin(theta) * r * radius
      seeds[i] = Math.random()
      radii[i] = (radius - 1.9) / 2.2
    }
    return { positions, seeds, radii }
  }, [])

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uLevel: { value: 0 },
      uColor: { value: new THREE.Color('#19c4c4') },
    }),
    [],
  )

  useFrame((state, dt) => {
    if (!mat.current) return
    const u = mat.current.uniforms
    u.uTime.value = state.clock.elapsedTime
    u.uLevel.value += (drive.level - u.uLevel.value) * Math.min(1, dt * 6)
    u.uColor.value.lerp(drive.color, Math.min(1, dt * 3))
  })

  return (
    <points frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-aSeed" args={[seeds, 1]} />
        <bufferAttribute attach="attributes-aRadius" args={[radii, 1]} />
      </bufferGeometry>
      <shaderMaterial
        ref={mat}
        uniforms={uniforms}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        transparent
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  )
}
