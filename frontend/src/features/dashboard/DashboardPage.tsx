// Dashboard: pulso general del macrociclo activo.
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Users, CalendarRange, TrendingUp, Trophy, ArrowRight, Waves,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../../lib/api'
import { toClock, signed } from '../../lib/format'
import { SPECIALTY_LABEL } from '../../lib/constants'
import { usePageEnter } from '../../hooks/usePageEnter'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, EmptyState, Spinner, StatusBadge, Chip } from '../../components/ui/primitives'
import { StatCard } from '../../components/ui/StatCard'
import { RingGauge } from '../../components/ui/RingGauge'
import { PhaseStrip } from './PhaseStrip'

export function DashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.dashboard.summary(),
    retry: false,
  })
  const ref = usePageEnter([data?.plan_id])

  if (isLoading) return <Spinner />
  if (isError || !data) {
    return (
      <div ref={ref}>
        <EmptyState
          icon={<Waves size={24} />}
          title="Sin macrociclo activo"
          hint="Crea tu primer macrociclo para empezar a planificar la temporada."
          action={<Link to="/macrociclos" className="btn btn-primary">Crear macrociclo <ArrowRight size={14} /></Link>}
        />
      </div>
    )
  }

  const nextComp = data.competitions
    .filter((c) => (c.weeks_away ?? -1) >= 0)
    .sort((a, b) => (a.weeks_away ?? 0) - (b.weeks_away ?? 0))[0]

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Dashboard"
        subtitle={
          <>
            {data.plan_name} · Semana {data.current_week ?? '—'} de {data.total_weeks}
            {data.current_phase && <> · Fase <span className="font-semibold text-violet-soft">{data.current_phase}</span></>}
          </>
        }
        actions={<Link to="/equipo" className="btn btn-primary">Tabla del equipo <ArrowRight size={14} /></Link>}
      />

      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="Atletas en plan" value={data.athletes_total} accent="#8b5cf6"
          icon={<Users size={15} />}
          sub={`${data.events_total} pruebas objetivo activas`}
        />
        <StatCard
          label="Semana actual" value={data.current_week ?? 0} suffix={`/ ${data.total_weeks}`}
          accent="#22d3ee" icon={<CalendarRange size={15} />}
          sub={data.current_phase ? `Fase ${data.current_phase}` : 'Fuera de calendario'}
        />
        <StatCard
          label="Estado del equipo" value={data.ahead} suffix="adelantados"
          accent="#34d399" icon={<TrendingUp size={15} />}
          sub={
            <span>
              <span className="text-cyan">{data.on_track} en plan</span>
              {' · '}
              <span className="text-coral">{data.behind} atrasados</span>
            </span>
          }
        />
        <StatCard
          label="Desviación media" value={data.avg_deviation_percent ?? 0} suffix="%" decimals={2}
          accent={data.avg_deviation_percent != null && data.avg_deviation_percent > 0 ? '#fb7185' : '#34d399'}
          icon={<Trophy size={15} />}
          sub="Real vs. plan (negativo = más rápido)"
        />
      </div>

      <div className="grid grid-cols-[1fr_300px] gap-4">
        <Card title="Progresión del equipo · % de mejora acumulada" className="card-hover">
          <ResponsiveContainer width="100%" height={252}>
            <AreaChart data={data.progression} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
              <defs>
                <linearGradient id="gradExpected" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradReal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(148,163,224,.06)" vertical={false} />
              <XAxis dataKey="date_label" tick={{ fill: '#8b93b8', fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace" }} tickLine={false} axisLine={false} />
              <YAxis unit="%" tick={{ fill: '#8b93b8', fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace" }} tickLine={false} axisLine={false} />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null
                  return (
                    <div className="card px-3.5 py-2.5 text-xs" style={{ background: '#11131f' }}>
                      <p className="mono mb-1 text-[10px] uppercase text-text-dim">{label}</p>
                      {payload.map((p) => (
                        <p key={String(p.dataKey)} className="flex items-center gap-2">
                          <span className="size-2 rounded-full" style={{ background: p.color }} />
                          <span className="text-text-dim">{p.name}:</span>
                          <span className="mono font-semibold">{(p.value as number)?.toFixed(1)}%</span>
                        </p>
                      ))}
                    </div>
                  )
                }}
              />
              {data.current_week && (
                <ReferenceLine
                  x={data.progression.find((p) => p.is_current)?.date_label}
                  stroke="#fbbf24" strokeDasharray="4 4" strokeOpacity={0.7}
                  label={{ value: 'Hoy', fill: '#fbbf24', fontSize: 10, position: 'top' }}
                />
              )}
              <Area type="monotone" dataKey="expected_progress" name="Planificado" stroke="#8b5cf6" strokeWidth={2} fill="url(#gradExpected)" dot={false} />
              <Area type="monotone" dataKey="real_progress" name="Real" stroke="#22d3ee" strokeWidth={2.5} fill="url(#gradReal)" connectNulls dot={{ r: 2.5, fill: '#22d3ee', strokeWidth: 0 }} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <div className="flex flex-col gap-4">
          <Card title="Registro semanal" className="card-hover flex flex-col items-center">
            <RingGauge
              value={data.compliance_percent} color="#22d3ee"
              label="Cumplimiento de registro"
              sublabel="Semanas con tiempo real ingresado"
            />
          </Card>
          {nextComp && (
            <Card className="card-hover glow-edge">
              <div className="flex items-center gap-2">
                <Trophy size={14} className="text-amber" />
                <span className="card-title !text-amber">Próxima competencia</span>
              </div>
              <p className="display mt-2 text-[15px] font-bold">{nextComp.name}</p>
              <p className="mt-1 text-[11.5px] text-text-dim">
                Semana {nextComp.week_number} · {nextComp.days} {nextComp.days === 1 ? 'día' : 'días'}
                {nextComp.is_main && <Chip color="#fbbf24"> Principal</Chip>}
              </p>
              <p className="display mt-2 text-2xl font-bold text-amber">
                {nextComp.weeks_away === 0 ? 'Esta semana' : `${nextComp.weeks_away} sem.`}
              </p>
            </Card>
          )}
        </div>
      </div>

      <Card title="Fases del macrociclo" className="card-hover">
        <PhaseStrip
          phases={data.phases}
          totalWeeks={data.total_weeks}
          currentWeek={data.current_week}
          competitions={data.competitions}
        />
      </Card>

      <Card title={`Estado por atleta · Semana ${data.current_week ?? '—'}`} className="card-hover">
        <table className="tbl">
          <thead>
            <tr>
              <th>Atleta</th><th>Especialidad</th><th>Prueba</th>
              <th>Esperado</th><th>Real</th><th>Diferencia</th>
              <th>Progreso a meta</th><th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {data.statuses.map((row) => (
              <tr key={row.event_id}>
                <td className="font-semibold">{row.name}</td>
                <td className="text-text-dim">{SPECIALTY_LABEL[row.specialty] ?? row.specialty}</td>
                <td className="text-text-dim">{row.event_label}</td>
                <td className="mono">{toClock(row.expected_time)}</td>
                <td className="mono font-semibold">{toClock(row.real_time)}</td>
                <td className="mono" style={{ color: row.diff_seconds == null ? '#565e82' : row.diff_seconds <= 0 ? '#34d399' : '#fb7185' }}>
                  {row.diff_seconds != null ? `${signed(row.diff_seconds)}s` : '—'}
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-3">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${Math.min(row.progress_percent, 100)}%`,
                          background: 'linear-gradient(90deg,#8b5cf6,#22d3ee)',
                        }}
                      />
                    </div>
                    <span className="mono text-[10.5px] text-text-dim">{row.progress_percent.toFixed(0)}%</span>
                  </div>
                </td>
                <td><StatusBadge status={row.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
