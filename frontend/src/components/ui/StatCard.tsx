// Tarjeta de métrica con número animado (count-up GSAP).
import type { CSSProperties, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { useCountUp } from '../../hooks/useCountUp'

export function StatCard({
  label, value, suffix = '', decimals = 0, sub, accent = '#3b82f6', icon, children, to,
}: {
  label: string
  value: number
  suffix?: string
  decimals?: number
  sub?: ReactNode
  accent?: string
  icon?: ReactNode
  children?: ReactNode
  // to: convierte la tarjeta en un enlace navegable a otra pantalla.
  to?: string
}) {
  const display = useCountUp(value, decimals)
  const body = (
    <>
      <div className="flex items-start justify-between">
        <span className="card-title inline-flex items-center gap-1">
          {label}
          {to && (
            <ArrowUpRight
              size={12}
              className="-translate-x-1 opacity-0 transition-all duration-200 group-hover:translate-x-0 group-hover:opacity-100"
              style={{ color: accent }}
            />
          )}
        </span>
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
    </>
  )

  // El glow del hover toma el acento propio de la tarjeta (--page-accent).
  const accentStyle = { '--page-accent': accent } as CSSProperties

  if (to) {
    return (
      <Link
        to={to}
        className="card card-hover group block cursor-pointer p-5"
        style={accentStyle}
        data-animate
      >
        {body}
      </Link>
    )
  }

  return (
    <div className="card card-hover p-5" style={accentStyle} data-animate>
      {body}
    </div>
  )
}
