// Vista Progresión: cómo va lo nadado contra lo planificado.
//
// Era la sección Comparación. Sus cuatro KPIs, su gráfico y su tabla de
// desviaciones salen todos de las MISMAS semanas que dibuja la vista Plan
// —filtradas a las que ya tienen tiempo real—, así que no había nada que pedir
// aparte: solo otra forma de mirar.
import { useMemo } from 'react'
import type { Week } from '../../lib/types'
import { STROKE_LABEL } from '../../lib/constants'
import { toClock, signed } from '../../lib/format'
import { Card, StatusBadge } from '../../components/ui/primitives'
import type { EventSelection } from '../../components/ui/EventPicker'
import { ProgressionChart } from '../../components/charts/ProgressionChart'
import { DeviationTable } from './DeviationTable'

export function VistaProgresion({
  weeks, selection,
}: { weeks: Week[]; selection: EventSelection }) {
  const stats = useMemo(() => {
    const withReal = weeks.filter((w) => w.real_time != null)
    if (!withReal.length) return { withReal, avgDiff: null, ahead: 0, on: 0, behind: 0, last: null }
    const avgDiff = withReal.reduce((acc, w) => acc + (w.diff_seconds ?? 0), 0) / withReal.length
    return {
      withReal,
      avgDiff,
      ahead: withReal.filter((w) => w.status === 'ahead').length,
      on: withReal.filter((w) => w.status === 'on_track').length,
      behind: withReal.filter((w) => w.status === 'behind').length,
      last: withReal[withReal.length - 1],
    }
  }, [weeks])

  return (
    <>
      <div className="grid grid-cols-4 gap-4">
        <Card className="card-hover">
          <p className="card-title">Último registro</p>
          <p className="display mt-1.5 text-[24px] font-bold text-mint">
            {stats.last ? toClock(stats.last.real_time) : '—'}
          </p>
          <p className="text-[10.5px] text-text-faint">
            {stats.last ? `Semana ${stats.last.week_number} (${stats.last.date_label})` : 'Sin tiempos reales aún'}
          </p>
        </Card>
        <Card className="card-hover">
          <p className="card-title">Desviación promedio</p>
          <p className="display mt-1.5 text-[24px] font-bold"
            style={{ color: stats.avgDiff == null ? '#565e82' : stats.avgDiff <= 0 ? '#34d399' : '#fb7185' }}>
            {stats.avgDiff != null ? `${signed(stats.avgDiff)}s` : '—'}
          </p>
          <p className="text-[10.5px] text-text-faint">Negativo = más rápido que el plan</p>
        </Card>
        <Card className="card-hover">
          <p className="card-title">Semanas evaluadas</p>
          <p className="display mt-1.5 text-[24px] font-bold text-cyan">{stats.withReal.length}</p>
          <p className="text-[10.5px] text-text-faint">
            <span className="text-mint">{stats.ahead} adelantado</span> ·{' '}
            <span className="text-cyan">{stats.on} en plan</span> ·{' '}
            <span className="text-coral">{stats.behind} atrasado</span>
          </p>
        </Card>
        <Card className="card-hover">
          <p className="card-title">Estado actual</p>
          <div className="mt-2.5">
            <StatusBadge status={stats.last?.status ?? null} />
          </div>
          <p className="mt-1.5 text-[10.5px] text-text-faint">
            Meta: <span className="mono text-amber">{toClock(selection.event.goal_time)}</span>
          </p>
        </Card>
      </div>

      <Card
        title={`Curva ideal vs. real · ${selection.event.distance}m ${STROKE_LABEL[selection.event.stroke]} · ${selection.athlete.swimmer_name}`}
        className="card-hover"
      >
        <ProgressionChart
          weeks={weeks}
          goalTime={selection.event.goal_time}
          height={340}
          currentWeek={selection.plan.current_week}
        />
        <div className="mt-2 flex gap-5 text-[10.5px] text-text-dim">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded bg-accent" /> Plan ideal</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded border-t-2 border-dashed border-cyan" /> Proyección ajustada</span>
          <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-mint" /> Tiempo real</span>
        </div>
      </Card>

      {stats.withReal.length > 0 && <DeviationTable weeks={stats.withReal} />}
    </>
  )
}
