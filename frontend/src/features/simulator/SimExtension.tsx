// Las dos tarjetas de EXTENSIÓN: el aviso de cuántas semanas extra harían falta,
// y la tabla que las detalla. La extensión es una estimación paralela — no
// modifica el plan del macro ni ningún cálculo del simulador.
import { CalendarClock, Repeat2 } from 'lucide-react'
import type { Feasibility, SimWeek } from '../../lib/types'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'
import { SimPlanTable } from './SimPlanTable'

/** Aviso: la meta supera el techo realista del macro en las semanas pedidas. */
export function SimExtensionNotice({ feasibility, weeks }: { feasibility: Feasibility; weeks: number }) {
  return (
    <Card title="Semanas adicionales estimadas" className="card-hover" animate={false}>
      <div className="flex items-start gap-3.5">
        <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl"
          style={{ color: '#fbbf24', background: '#fbbf2416', border: '1px solid #fbbf2433' }}>
          <CalendarClock size={17} />
        </span>
        <div className="flex-1">
          <p className="text-[12px] leading-relaxed text-text-dim">
            La meta supera el techo realista en {weeks} semanas. El motor estima
            cuántas necesitarías y detalla cada una en la <span className="font-semibold text-text">tabla de extensión</span> de abajo
            — <span className="font-semibold text-text">no modifica tu plan ni ningún cálculo</span>.
          </p>
          <table className="tbl mt-3">
            <tbody>
              <tr>
                <td className="text-text-dim">Semanas del plan actual</td>
                <td className="mono text-right">{weeks}</td>
              </tr>
              <tr>
                <td className="text-text-dim">Semanas estimadas para la meta</td>
                <td className="mono text-right">{feasibility.recommended_weeks}</td>
              </tr>
              <tr>
                <td className="font-semibold">Semanas extra (tabla de extensión)</td>
                <td className="mono text-right font-bold" style={{ color: '#fbbf24' }}>
                  +{feasibility.extension_weeks ?? Math.max(0, (feasibility.recommended_weeks ?? weeks) - weeks)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  )
}

/** Las semanas de extensión, detalladas igual que el plan del macro. */
export function SimExtensionTable(
  { extensionWeeks, feasibility, weeks }: { extensionWeeks: SimWeek[]; feasibility: Feasibility; weeks: number },
) {
  return (
    <Card
      title={`Semanas de extensión · +${extensionWeeks.length} (continuación realista hasta la meta)`}
      className="card-hover" animate={false} flush
    >
      <div className="flex items-center gap-2.5 px-4 pt-3.5">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-lg"
          style={{ color: '#fbbf24', background: '#fbbf2416', border: '1px solid #fbbf2433' }}>
          <Repeat2 size={14} />
        </span>
        <p className="text-[11.5px] leading-relaxed text-text-dim">
          El macro de {weeks} sem cierra en el techo realista
          (<span className="mono font-semibold text-text">{toClock(feasibility.realistic_ceiling)}</span>);
          estas semanas continúan al ritmo seguro hasta la meta. Total estimado:{' '}
          <span className="font-semibold" style={{ color: '#fbbf24' }}>{feasibility.recommended_weeks} semanas</span>.
        </p>
      </div>
      <div className="mt-2.5">
        <SimPlanTable weeks={extensionWeeks} extension />
      </div>
    </Card>
  )
}
