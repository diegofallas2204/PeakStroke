// Fondo WebGL: malla de ondas con shader propio (Three.js).
// Muy sutil, detrás de toda la interfaz; evoca la superficie de la piscina.
import { useEffect, useRef } from 'react'
import * as THREE from 'three'

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
  varying float vElevation;
  void main() {
    float t = smoothstep(-1.2, 1.2, vElevation);
    vec3 violet = vec3(0.545, 0.361, 0.965);
    vec3 cyan = vec3(0.133, 0.827, 0.933);
    vec3 color = mix(violet, cyan, t);
    float alpha = 0.10 + t * 0.16;
    gl_FragColor = vec4(color, alpha);
  }
`

export function WaveBackground() {
  const mountRef = useRef<HTMLDivElement>(null)

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

    const geometry = new THREE.PlaneGeometry(46, 30, 110, 70)
    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX,
      fragmentShader: FRAGMENT,
      uniforms: { uTime: { value: 0 } },
      transparent: true,
      depthWrite: false,
    })
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
      geometry.dispose()
      material.dispose()
      renderer.dispose()
      mount.removeChild(renderer.domElement)
    }
  }, [])

  return (
    <div
      ref={mountRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0"
      style={{
        opacity: 0.55,
        maskImage: 'radial-gradient(ellipse 90% 70% at 60% 30%, black 30%, transparent 75%)',
        WebkitMaskImage: 'radial-gradient(ellipse 90% 70% at 60% 30%, black 30%, transparent 75%)',
      }}
    />
  )
}
