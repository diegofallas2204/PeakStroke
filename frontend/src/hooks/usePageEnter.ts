// Animación de entrada de página: stagger fade-up de los bloques marcados
// con [data-animate] dentro del contenedor.
import { useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'

export function usePageEnter<T extends HTMLElement = HTMLDivElement>(deps: unknown[] = []) {
  const ref = useRef<T>(null)

  useLayoutEffect(() => {
    const root = ref.current
    if (!root) return
    const targets = root.querySelectorAll('[data-animate]')
    if (!targets.length) return
    const ctx = gsap.context(() => {
      gsap.fromTo(
        targets,
        { opacity: 0, y: 18, scale: 0.995 },
        {
          opacity: 1, y: 0, scale: 1,
          duration: 0.55, ease: 'power3.out', stagger: 0.06,
          clearProps: 'transform',
        },
      )
    }, root)
    return () => ctx.revert()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return ref
}
