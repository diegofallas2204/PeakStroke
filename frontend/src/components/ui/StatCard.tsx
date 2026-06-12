// Tarjeta de métrica con número animado (count-up GSAP).
import type { ReactNode } from 'react'
import { useCountUp } from '../../hooks/useCountUp'

export function StatCard({
  label, value, suffix = '', decimals = 0, sub, accent = '#8b5cf6', icon, children,
}: {
  label: string
  value: number
  suffix?: string
  decimals?: number
  sub?: ReactNode
  accent?: string
  icon?: ReactNode
  children?: ReactNode
}) {
  const display = useCountUp(value, decimals)
  return (
    <div className="card card-hover p-5" data-animate>
      <div className="flex items-start justify-between">
        <span className="card-title">{label}</span>
        {icon && (
          <span
            className="flex size-8 items-center justify-center rounded-lg"
            style={{ color: accent, background: `${accent}1a` }}
          >
            {icon}
          </span>
        )}
      </div>
      <div className="display mt-2 text-[28px] font-bold leading-none" style={{ color: accent }}>
        {display}
        {suffix && <span className="ml-1 text-base font-semibold text-text-dim">{suffix}</span>}
      </div>
      {sub && <div className="mt-2 text-[11.5px] text-text-dim">{sub}</div>}
      {children}
    </div>
  )
}
