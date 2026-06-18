// Fondo WebGL: malla de ondas con shader propio (Three.js).
// Muy sutil, detrás de toda la interfaz; evoca la superficie de la piscina.
// Los colores y la opacidad se adaptan al tema: en el tema blanco se intensifican
// (tonos más oscuros y mayor alfa) para que los puntos se aprecien sobre el claro.
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { useTheme, type Theme } from '../../hooks/useTheme'

const VERTEX = /* glsl */ `
  uniform float uTime;
  varying float vElevation;
  void main() {
    vec3 pos = position;
    float e1 = sin(pos.x * 0.55 + uTime * 0.55) * 0.45;
    float e2 = sin(pos.y * 0.40 + uTime * 0.35) * 0.35;
    float e3 = sin((pos.x + pos.y) * 0.25 + uTime * 0.22) * 0.55;
    pos.z = e1 + e2 + e3;
    vElevation = pos.z;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
    gl_PointSize = 1.6;
  }
`

const FRAGMENT = /* glsl */ `
  uniform vec3 uColorLow;
  uniform vec3 uColorHigh;
  uniform float uAlphaBase;
  uniform float uAlphaScale;
  varying float vElevation;
  void main() {
    float t = smoothstep(-1.2, 1.2, vElevation);
    vec3 color = mix(uColorLow, uColorHigh, t);
    float alpha = uAlphaBase + t * uAlphaScale;
    gl_FragColor = vec4(color, alpha);
  }
`

interface WaveLook {
  low: THREE.Color
  high: THREE.Color
  alphaBase: number
  alphaScale: number
  opacity: number
}

function lookFor(theme: Theme): WaveLook {
  if (theme === 'white') {
    // Azul/cian profundos y más opacos para destacar sobre fondo claro.
    return {
      low: new THREE.Color(0.114, 0.306, 0.847),   // #1d4ed8
      high: new THREE.Color(0.031, 0.569, 0.698),   // #0891b2
      alphaBase: 0.32,
      alphaScale: 0.42,
      opacity: 0.85,
    }
  }
  return {
    low: new THREE.Color(0.231, 0.510, 0.965),      // #3b82f6
    high: new THREE.Color(0.133, 0.827, 0.933),      // #22d3ee
    alphaBase: 0.1,
    alphaScale: 0.16,
    opacity: 0.55,
  }
}

export function WaveBackground() {
  const [theme] = useTheme()
  const mountRef = useRef<HTMLDivElement>(null)
  const materialRef = useRef<THREE.ShaderMaterial | null>(null)
  const themeRef = useRef<Theme>(theme)
  themeRef.current = theme

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.setSize(window.innerWidth, window.innerHeight)
    mount.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 100)
    camera.position.set(0, -7.5, 5.5)
    camera.lookAt(0, 2, 0)

    const look = lookFor(themeRef.current)
    const geometry = new THREE.PlaneGeometry(46, 30, 110, 70)
    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX,
      fragmentShader: FRAGMENT,
      uniforms: {
        uTime: { value: 0 },
        uColorLow: { value: look.low },
        uColorHigh: { value: look.high },
        uAlphaBase: { value: look.alphaBase },
        uAlphaScale: { value: look.alphaScale },
      },
      transparent: true,
      depthWrite: false,
    })
    materialRef.current = material
    const points = new THREE.Points(geometry, material)
    points.rotation.x = -Math.PI / 2.6
    scene.add(points)

    const start = performance.now()
    let raf = 0
    let running = true

    const tick = () => {
      if (!running) return
      material.uniforms.uTime.value = (performance.now() - start) / 1000
      renderer.render(scene, camera)
      raf = requestAnimationFrame(tick)
    }
    tick()

    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight
      camera.updateProjectionMatrix()
      renderer.setSize(window.innerWidth, window.innerHeight)
    }
    const onVisibility = () => {
      running = document.visibilityState === 'visible'
      if (running) tick()
      else cancelAnimationFrame(raf)
    }
    window.addEventListener('resize', onResize)
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      running = false
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      document.removeEventListener('visibilitychange', onVisibility)
      materialRef.current = null
      geometry.dispose()
      material.dispose()
      renderer.dispose()
      mount.removeChild(renderer.domElement)
    }
  }, [])

  // Reacciona al cambio de tema sin recrear la escena.
  useEffect(() => {
    const material = materialRef.current
    if (!material) return
    const look = lookFor(theme)
    material.uniforms.uColorLow.value = look.low
    material.uniforms.uColorHigh.value = look.high
    material.uniforms.uAlphaBase.value = look.alphaBase
    material.uniforms.uAlphaScale.value = look.alphaScale
    if (mountRef.current) mountRef.current.style.opacity = String(look.opacity)
  }, [theme])

  return (
    <div
      ref={mountRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0"
      style={{
        opacity: lookFor(theme).opacity,
        maskImage: 'radial-gradient(ellipse 90% 70% at 60% 30%, black 30%, transparent 75%)',
        WebkitMaskImage: 'radial-gradient(ellipse 90% 70% at 60% 30%, black 30%, transparent 75%)',
      }}
    />
  )
}
