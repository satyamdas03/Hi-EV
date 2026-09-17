import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { Drive } from './Scene'

const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const fragmentShader = `
  uniform vec3 uColor;
  uniform float uLevel;
  uniform float uPhase;
  uniform float uOpen;
  varying vec2 vUv;

  float band(float r, float r0, float w) {
    return exp(-pow((r - r0) / w, 2.0));
  }

  void main() {
    vec2 p = (vUv * 2.0 - 1.0) * 1.2;
    float r = length(p);
    float a = atan(p.y, p.x);

    float R = 0.74 + sin(uPhase * 0.5 + a * 3.0) * 0.02 + uLevel * 0.03;

    float ring = band(r, R, 0.03) * 0.8;
    float inner = band(r, R - 0.06, 0.025) * 0.35;
    float core = smoothstep(0.42, 0.36, r) * (0.08 + uLevel * 0.15);
    float sweep = smoothstep(-0.3, 0.0, mod(a - uPhase * 0.8, 6.28) - 3.14) * band(r, R, 0.08) * (0.4 + uLevel * 0.4);

    float v = (ring + inner + core + sweep);
    v *= smoothstep(0.0, 0.4, uOpen - r * 0.5);

    gl_FragColor = vec4(uColor * v, v);
  }
`

export function Core({ drive }: { drive: Drive }) {
  const mat = useRef<THREE.ShaderMaterial>(null)

  const uniforms = useMemo(
    () => ({
      uColor: { value: new THREE.Color('#19c4c4') },
      uLevel: { value: 0 },
      uPhase: { value: 0 },
      uOpen: { value: 0 },
    }),
    [],
  )

  useFrame((_, dt) => {
    if (!mat.current) return
    const u = mat.current.uniforms
    u.uLevel.value += (drive.level - u.uLevel.value) * Math.min(1, dt * 8)
    u.uPhase.value += dt * (0.6 + drive.level * 1.2)
    u.uOpen.value += (drive.open - u.uOpen.value) * Math.min(1, dt * 1.5)
    u.uColor.value.lerp(drive.color, Math.min(1, dt * 2.5))
  })

  return (
    <mesh frustumCulled={false}>
      <planeGeometry args={[5.4, 5.4]} />
      <shaderMaterial
        ref={mat}
        uniforms={uniforms}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        transparent
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  )
}
