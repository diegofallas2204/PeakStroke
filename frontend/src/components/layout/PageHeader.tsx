// Encabezado estándar de página: título, subtítulo y acciones.
import type { ReactNode } from 'react'

export function PageHeader({
  title, subtitle, actions,
}: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3" data-animate>
      <div>
        <h1 className="display text-[22px] font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-xs text-text-dim">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2.5">{actions}</div>}
    </header>
  )
}
