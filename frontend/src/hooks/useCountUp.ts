// Número animado con GSAP (count-up con snap al renderizar/cambiar valor).
import { useEffect, useRef, useState } from 'react'
import gsap from 'gsap'

export function useCountUp(value: number, decimals = 0, duration = 1.1): string {
  const [display, setDisplay] = useState('0')
  const proxy = useRef({ v: 0 })

  useEffect(() => {
    const obj = proxy.current
    const tween = gsap.to(obj, {
      v: value,
      duration,
      ease: 'power2.out',
      onUpdate: () => setDisplay(obj.v.toFixed(decimals)),
    })
    return () => {
      tween.kill()
    }
  }, [value, decimals, duration])

  return display
}
