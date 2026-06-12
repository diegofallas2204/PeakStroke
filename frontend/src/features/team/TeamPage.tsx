// Tabla del equipo: todos los atletas en una semana del macrociclo con sus
// tiempos objetivo por zona. Incluye gráfico colapsable de progreso promedio.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Table2 } from 'lucide-react'
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../../lib/api'
import { SPECIALTY_LABEL, ZONE_META, ZONE_ORDER } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, EmptyState, Spinner, StatusBadge } from '../../components/ui/primitives'

export function TeamPage() {
  const [week, setWeek] = useState<number | null>(null)
  const [showChart, setShowChart] = useState(true)

  const { data: summary } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.dashboard.summary(),
    retry: false,
  })
  const { data, isLoading, isError } = useQuery({
    queryKey: ['team-week', week],
    queryFn: () => api.dashboard.teamWeek(undefined, week ?? undefined),
    retry: false,
  })

  const ref = usePageEnter([data?.week_number, isLoading])

  if (isLoading) return <Spinner />
  if (isError || !data) {
    return (
      <div ref={ref}>
        <PageHeader title="Tabla del equipo" />
        <EmptyState icon={<Table2 size={24} />} title="Sin macrociclo activo"
          hint="Activa un macrociclo con atletas asignados para ver la tabla semanal del equipo." />
      </div>
    )
  }

  const totalWeeks = summary?.total_weeks ?? 18
  const currentWeek = data.week_number

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Tabla del equipo"
        subtitle={`Semana ${currentWeek} · ${data.date_label}${data.phase ? ` · Fase ${data.phase}` : ''} — tiempos a exigir por zona (pace /100m)`}
        actions={
          <div className="flex items-center gap-2">
            <button className="btn btn-ghost !p-2" disabled={currentWeek <= 1}
              onClick={() => setWeek(currentWeek - 1)} aria-label="Semana anterior">
              <ChevronLeft size={15} />
            </button>
            <span className="mono min-w-20 text-center text-[12.5px] font-bold">
              S{currentWeek} / {totalWeeks}
            </span>
            <button className="btn btn-ghost !p-2" disabled={currentWeek >= totalWeeks}
              onClick={() => setWeek(currentWeek + 1)} aria-label="Semana siguiente">
              <ChevronRight size={15} />
            </button>
            {summary?.current_week && summary.current_week !== currentWeek && (
              <button className="btn btn-ghost text-[11px]" onClick={() => setWeek(summary.current_week)}>
                Hoy
              </button>
            )}
          </div>
        }
      />

      {summary && (
        <Card animate
          title={
            <button className="flex items-center gap-2" onClick={() => setShowChart((s) => !s)}>
              Progreso promedio del equipo
              {showChart ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          }
          className="card-hover"
        >
          {showChart && (
            <ResponsiveContainer width="100%" height={130}>
              <AreaChart data={summary.progression} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                <defs>
                  <linearGradient id="teamGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date_label" tick={{ fill: '#8b93b8', fontSize: 9.5, fontFamily: "'JetBrains Mono', monospace" }} tickLine={false} axisLine={false} />
                <YAxis unit="%" tick={{ fill: '#8b93b8', fontSize: 9.5 }} tickLine={false} axisLine={false} />
                <Tooltip
                  content={({ active, payload, label }) => active && payload?.length ? (
                    <div className="card px-3 py-2 text-[11px]" style={{ background: '#11131f' }}>
                      <span className="text-text-dim">{label}: </span>
                      <span className="mono font-bold">{(payload[0].value as number)?.toFixed(1)}%</span>
                    </div>
                  ) : null}
                />
                <Area type="monotone" dataKey="expected_progress" name="Planificado" stroke="#8b5cf6" strokeWidth={1.6} fill="transparent" dot={false} strokeDasharray="5 4" />
                <Area type="monotone" dataKey="real_progress" name="Real" stroke="#22d3ee" strokeWidth={2.2} fill="url(#teamGrad)" connectNulls dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
      )}

      <Card className="card-hover !p-0" animate>
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead>
              <tr>
                <th>Atleta</th><th>Prueba</th><th>Esperado</th><th>Pace /100</th>
                {ZONE_ORDER.map((z) => (
                  <th key={z} style={{ color: ZONE_META[z].color }}>{z}</th>
                ))}
                <th>Km</th><th>Real</th><th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={row.event_id} style={{ opacity: row.disabled ? 0.4 : 1 }}>
                  <td>
                    <p className="font-semibold">{row.name}</p>
                    <p className="text-[9.5px] text-text-faint">{SPECIALTY_LABEL[row.specialty] ?? row.specialty}</p>
                  </td>
                  <td className="text-text-dim">{row.event_label}</td>
                  <td className="mono">{toClock(row.expected_time)}</td>
                  <td className="mono font-semibold text-violet-soft">{toClock(row.pace_100m)}</td>
                  {ZONE_ORDER.map((zone) => {
                    const range = row.zones?.[zone]
                    return (
                      <td key={zone} className="mono text-[11.5px]">
                        {range ? (
                          <div>
                            <span style={{ color: ZONE_META[zone].color }}>{toClock(range.mid, 1)}</span>
                            {row.zone_km?.[zone] != null && (
                              <p className="text-[9px] text-text-faint">{row.zone_km[zone]} km</p>
                            )}
                          </div>
                        ) : (
                          <span className="text-text-faint">—</span>
                        )}
                      </td>
                    )
                  })}
                  <td className="mono">{row.planned_km ?? '—'}</td>
                  <td className="mono font-semibold">{toClock(row.real_time)}</td>
                  <td>
                    {row.disabled
                      ? <span className="text-[10px] uppercase tracking-wide text-text-faint">Parón</span>
                      : row.status
                        ? <StatusBadge status={row.status} />
                        : <span className="text-[10.5px] text-text-faint">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="border-t border-line px-4 py-2.5 text-[10px] text-text-faint">
          Tiempo por zona = punto medio del rango (factores por distancia de la prueba).
          Km por zona = distribución sugerida según la especialidad del atleta.
        </p>
      </Card>
    </div>
  )
}
