// Encabezado estándar de página: título, subtítulo y acciones.
// Lleva una barra de acento con el color distintivo de la sección (misma fuente
// que el indicador del sidebar) para que cada página sea identificable de un vistazo.
import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { SECTION_ACCENT } from '../../lib/constants'

export function PageHeader({
  title, subtitle, actions, accent,
}: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; accent?: string }) {
  const { pathname } = useLocation()
  const color = accent ?? SECTION_ACCENT[pathname] ?? 'var(--color-accent)'

  return (
    <header className="flex flex-wrap items-end justify-between gap-3 pb-1" data-animate>
      <div className="flex items-stretch gap-3.5">
        <span
          className="w-[3px] shrink-0 rounded-full"
          style={{ background: `linear-gradient(180deg, ${color}, ${color}55)` }}
        />
        <div>
          <h1 className="display text-[24px] font-bold leading-none tracking-[-0.02em]">{title}</h1>
          {subtitle && <p className="mt-1.5 text-[12px] leading-relaxed text-text-dim">{subtitle}</p>}
        </div>
      </div>
      {/* `flex-wrap`: en móvil un selector, un rango y un botón no caben en
          375 px, y sin él la fila empujaba la página entera a scroll lateral. */}
      {actions && <div className="flex flex-wrap items-center gap-2.5">{actions}</div>}
    </header>
  )
}
