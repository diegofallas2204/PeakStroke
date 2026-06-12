// Indicador circular animado (estilo "score" de las referencias visuales).
import { useEffect, useRef } from 'react'
import gsap from 'gsap'

export function RingGauge({
  value, max = 100, size = 132, stroke = 10, color = '#8b5cf6', track = 'rgba(148,163,224,.1)',
  label, sublabel,
}: {
  value: number
  max?: number
  size?: number
  stroke?: number
  color?: string
  track?: string
  label?: string
  sublabel?: string
}) {
  const circleRef = useRef<SVGCircleElement>(null)
  const textRef = useRef<SVGTextElement>(null)
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const fraction = Math.max(0, Math.min(value / max, 1))

  useEffect(() => {
    const circle = circleRef.current
    const text = textRef.current
    if (!circle || !text) return
    const proxy = { f: 0 }
    const tween = gsap.to(proxy, {
      f: fraction,
      duration: 1.4,
      ease: 'power3.out',
      onUpdate: () => {
        circle.style.strokeDashoffset = String(circumference * (1 - proxy.f))
        text.textContent = `${Math.round(proxy.f * max)}${max === 100 ? '%' : ''}`
      },
    })
    return () => {
      tween.kill()
    }
  }, [fraction, circumference, max])

  return (
    <div className="relative inline-flex flex-col items-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={track} strokeWidth={stroke} />
        <circle
          ref={circleRef}
          cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={circumference}
          style={{ filter: `drop-shadow(0 0 8px ${color}66)` }}
        />
        <text
          ref={textRef}
          x="50%" y="50%"
          className="display rotate-90"
          style={{ transformOrigin: 'center' }}
          textAnchor="middle" dominantBaseline="central"
          fill="#e7eaf6" fontSize={size / 5.2} fontWeight={700}
        >
          0
        </text>
      </svg>
      {label && <span className="mt-1 text-[11px] font-semibold text-text-dim">{label}</span>}
      {sublabel && <span className="text-[10px] text-text-faint">{sublabel}</span>}
    </div>
  )
}
