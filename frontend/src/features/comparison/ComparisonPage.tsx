// Comparación real vs. planificado: curvas de progresión y resumen de
// desviaciones del atleta seleccionado.
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GitCompareArrows } from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../../lib/api'
import { STROKE_LABEL } from '../../lib/constants'
import { toClock, signed } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, EmptyState, Spinner, StatusBadge } from '../../components/ui/primitives'
import { EventPicker, type EventSelection } from '../../components/ui/EventPicker'
import { ProgressionChart } from '../../components/charts/ProgressionChart'
import { ChartTooltip } from '../../components/charts/chartTheme'

export function ComparisonPage() {
  const [selection, setSelection] = useState<EventSelection | null>(null)

  const { data: weeks, isLoading } = useQuery({
    queryKey: ['weeks', selection?.event.id],
    queryFn: () => api.plans.eventWeeks(selection!.event.id),
    enabled: selection != null,
  })

  const stats = useMemo(() => {
    if (!weeks) return null
    const withReal = weeks.filter((w) => w.real_time != null)
    if (!withReal.length) return { withReal: [], avgDiff: null, ahead: 0, on: 0, behind: 0, last: null }
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

  const ref = usePageEnter([selection?.event.id, isLoading])

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Comparación"
        subtitle="Curva ideal vs. proyección ajustada vs. rendimiento real"
      />
      <EventPicker onChange={setSelection} />

      {!selection ? (
        <EmptyState icon={<GitCompareArrows size={24} />} title="Sin datos"
          hint="Asigna atletas a un macrociclo para comparar su rendimiento." />
      ) : isLoading || !weeks || !stats ? (
        <Spinner />
      ) : (
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
              height={300}
              currentWeek={selection.plan.current_week}
            />
          </Card>

          {stats.withReal.length > 0 && (
            <Card title="Desviación semanal (segundos vs. plan)" className="card-hover">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={stats.withReal} margin={{ top: 6, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(148,163,224,.06)" vertical={false} />
                  <XAxis dataKey="date_label" tick={{ fill: '#8b93b8', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: '#8b93b8', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v}s`} />
                  <Tooltip content={<ChartTooltip formatter={(v: number) => `${signed(v)}s`} />} cursor={{ fill: 'rgba(148,163,224,.04)' }} />
                  <ReferenceLine y={0} stroke="rgba(148,163,224,.25)" />
                  <Bar dataKey="diff_seconds" name="Desviación" radius={[5, 5, 5, 5]} maxBarSize={26}>
                    {stats.withReal.map((w) => (
                      <Cell key={w.id} fill={(w.diff_seconds ?? 0) <= 0 ? '#34d399' : '#fb7185'} fillOpacity={0.85} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
