// La tarjeta de EXTENSIÓN: las semanas que harían falta después del macro.
// Cuántas son ya lo dice el veredicto (`SimFeasibility`); hasta el 2026-11-13
// había además una tarjeta de aviso que repetía las dos cosas. La extensión es una estimación paralela — no
// modifica el plan del macro ni ningún cálculo del simulador.
import { Repeat2 } from 'lucide-react'
import type { Feasibility, SimWeek } from '../../lib/types'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'
import { SimPlanTable } from './SimPlanTable'

/** Las semanas de extensión, detalladas igual que el plan del macro. */
export function SimExtensionTable(
  { extensionWeeks, feasibility, weeks }: { extensionWeeks: SimWeek[]; feasibility: Feasibility; weeks: number },
) {
  return (
    <Card
      title={`Semanas de extensión · +${extensionWeeks.length}`}
      className="card-hover" animate={false} flush
    >
      <div className="flex items-center gap-2.5 px-4 pt-3.5">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-lg"
          style={{ color: '#fbbf24', background: '#fbbf2416', border: '1px solid #fbbf2433' }}>
          <Repeat2 size={14} />
        </span>
        <p className="text-[11.5px] leading-relaxed text-text-dim">
          Las {weeks} semanas cierran en{' '}
          <span className="mono font-semibold text-text">{toClock(feasibility.realistic_ceiling)}</span>;
          estas siguen al ritmo seguro hasta la meta. No cambian el plan.
        </p>
      </div>
      <div className="mt-2.5">
        <SimPlanTable weeks={extensionWeeks} extension />
      </div>
    </Card>
  )
}
