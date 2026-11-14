// Dashboard: pulso general del macrociclo de trabajo.
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Trophy, ArrowRight, Waves, ChevronsUpDown, Plus } from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api, esNoEncontrado } from '../../lib/api'
import { finDeMacro } from '../../lib/format'
import { setSelectedPlan } from '../../hooks/useSelectedPlan'
import { ErrorDeCarga } from '../../components/ui/ErrorDeCarga'
import { PLAN_STATUS_META } from '../../lib/constants'
import { usePageEnter } from '../../hooks/usePageEnter'
import { useSelectedPlanId } from '../../hooks/useSelectedPlan'
import { useSimpleMode } from '../../hooks/useSimpleMode'
import { useRole } from '../../hooks/useSession'
import { PageHeader } from '../../components/layout/PageHeader'
import { weekDateTick } from '../../components/charts/weekAxisTick'
import { Card, EmptyState, Spinner, Chip } from '../../components/ui/primitives'
import { RingGauge } from '../../components/ui/RingGauge'
import { DashboardStats } from './DashboardStats'
import { EstadoTable } from './EstadoTable'
import { PhaseStrip } from './PhaseStrip'
import { vistaPara } from './vistaPorRol'
import { MacroSwitcherModal } from '../plans/MacroSwitcherModal'

export function DashboardPage() {
  const selectedId = useSelectedPlanId()
  const [switcherOpen, setSwitcherOpen] = useState(false)
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['dashboard', selectedId],
    queryFn: () => api.dashboard.summary(selectedId ?? undefined),
    retry: false,
  })
  const [simple] = useSimpleMode()
  const vista = vistaPara(useRole())
  const ref = usePageEnter([data?.plan_id])

  // Un 404 con un macro elegido es una selección vieja (lo borraron o ya no es
  // visible): se olvida y se vuelve al activo, en vez de decir «no hay ninguno».
  // En un efecto: cambiar la selección avisa a otros componentes (el riel).
  const seleccionVieja = isError && esNoEncontrado(error) && selectedId != null
  useEffect(() => {
    if (seleccionVieja) setSelectedPlan(null)
  }, [seleccionVieja])

  if (isLoading) return <Spinner />
  if (seleccionVieja) return <Spinner />
  // Cualquier otro fallo es un fallo, no un vacío: antes, con el backend caído,
  // Inicio decía «Sin macrociclo activo» y ofrecía crear uno.
  if (isError && !esNoEncontrado(error)) {
    return (
      <div ref={ref}>
        <ErrorDeCarga error={error} que="el inicio" onReintentar={() => void refetch()} reintentando={isFetching} />
      </div>
    )
  }
  if (isError || !data) {
    // El vacío del atleta no es el del entrenador: él no puede crear un
    // macrociclo, así que ofrecerle el botón sería mandarle a una ruta que la
    // guarda rebota. Ver `vistaPorRol`.
    return (
      <div ref={ref}>
        <EmptyState
          icon={<Waves size={24} />}
          title={vista.vacio.titulo}
          hint={vista.vacio.pista}
          action={vista.vacio.accion && (
            <Link to={vista.vacio.accion.a} className="btn btn-primary">
              {vista.vacio.accion.texto} <ArrowRight size={14} />
            </Link>
          )}
        />
      </div>
    )
  }

  // Con el calendario terminado no hay «próxima»: lo dice el backend
  // (`weeks_away` ya cuenta desde hoy, no desde la última semana).
  const nextComp = data.competitions
    .filter((c) => (c.weeks_away ?? -1) >= 0)
    .sort((a, b) => (a.weeks_away ?? 0) - (b.weeks_away ?? 0))[0]

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Inicio"
        subtitle={
          <span className="inline-flex flex-wrap items-center gap-x-1.5 gap-y-1">
            {data.is_over ? (
              <span>Terminó el {finDeMacro(data.start_date, data.total_weeks)} · {data.total_weeks} semanas</span>
            ) : (
              <span>Semana {data.current_week ?? '—'} de {data.total_weeks}</span>
            )}
            {data.current_phase && <span> · Fase <span className="font-semibold text-accent-soft">{data.current_phase}</span></span>}
            <Chip color={(PLAN_STATUS_META[data.plan_status] ?? PLAN_STATUS_META.draft).color}>
              {(PLAN_STATUS_META[data.plan_status] ?? PLAN_STATUS_META.draft).label}
            </Chip>
          </span>
        }
        actions={
          <>
            {/* El nombre del macrociclo ES el selector: dice cuál se mira y se
                abre como un desplegable, sin gastar dos palabras en decirlo. */}
            <button
              className="btn btn-ghost min-w-0"
              onClick={() => setSwitcherOpen(true)}
              aria-label={`Cambiar macrociclo (ahora: ${data.plan_name})`}
              title="Cambiar macrociclo"
            >
              <span className="truncate">{data.plan_name}</span>
              <ChevronsUpDown size={14} className="shrink-0 text-text-dim" />
            </button>
            {vista.accionRapida && (
              <Link to={vista.accionRapida.a} className="btn btn-primary">
                <Plus size={14} /> {vista.accionRapida.texto}
              </Link>
            )}
            {/* Con una acción rápida delante, la principal baja a secundaria:
                dos botones primarios juntos no dicen cuál es el de hoy. */}
            {vista.accion && (
              <Link to={vista.accion.a} className={`btn ${vista.accionRapida ? 'btn-ghost' : 'btn-primary'}`}>
                {vista.accion.texto} <ArrowRight size={14} />
              </Link>
            )}
          </>
        }
      />
      <MacroSwitcherModal open={switcherOpen} onClose={() => setSwitcherOpen(false)} />

      <DashboardStats data={data} vista={vista} simple={simple} />

      {!simple && (
        <div className="grid gap-4 [&>*]:min-w-0 lg:grid-cols-[1fr_300px]">
          <Card title={vista.tituloProgresion} className="card-hover flex flex-col">
            <div className="min-h-[252px] flex-1">
              <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.progression} margin={{ top: 20, right: 8, left: -18, bottom: 6 }}>
                <defs>
                  <linearGradient id="gradExpected" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0.04} />
                  </linearGradient>
                  <linearGradient id="gradReal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-cyan)" stopOpacity={0.45} />
                    <stop offset="100%" stopColor="var(--color-cyan)" stopOpacity={0.04} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--color-grid)" vertical={false} />
                <XAxis dataKey="date_label" interval="preserveStartEnd" minTickGap={16} height={34} tick={weekDateTick(data.progression)} tickLine={false} axisLine={false} />
                <YAxis unit="%" tick={{ fill: 'var(--color-text-dim)', fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace" }} tickLine={false} axisLine={false} />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null
                    return (
                      <div className="card px-3.5 py-2.5 text-xs">
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
                {data.progression.some((p) => p.is_current) && (
                  <ReferenceLine
                    x={data.progression.find((p) => p.is_current)?.date_label}
                    stroke="var(--color-amber)" strokeDasharray="4 4" strokeOpacity={0.7}
                    label={{ value: 'Hoy', fill: 'var(--color-amber)', fontSize: 10, position: 'top' }}
                  />
                )}
                <Area type="monotone" dataKey="expected_progress" name="Planificado" stroke="var(--color-accent)" strokeWidth={2} fill="url(#gradExpected)" dot={false} />
                <Area type="monotone" dataKey="real_progress" name="Real" stroke="var(--color-cyan)" strokeWidth={2.5} fill="url(#gradReal)" connectNulls dot={{ r: 2.5, fill: 'var(--color-cyan)', strokeWidth: 0 }} />
              </AreaChart>
            </ResponsiveContainer>
            </div>
          </Card>

          <div className="flex flex-col gap-4">
            <Card title="Registro semanal" className="card-hover flex flex-col items-center">
              <RingGauge
                value={data.compliance_percent} color="#22d3ee"
                label="Semanas con tiempo real"
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
                  {nextComp.is_main && <span className="ml-1.5"><Chip color="#fbbf24">Principal</Chip></span>}
                </p>
                <p className="display mt-2 text-2xl font-bold text-amber">
                  {nextComp.weeks_away === 0 ? 'Esta semana' : nextComp.weeks_away === 1 ? 'En 1 semana' : `En ${nextComp.weeks_away} semanas`}
                </p>
              </Card>
            )}
          </div>
        </div>
      )}

      {simple && nextComp && (
        <Card className="card-hover glow-edge">
          <div className="flex items-center gap-2">
            <Trophy size={14} className="text-amber" />
            <span className="card-title !text-amber">Próxima competencia</span>
          </div>
          <p className="display mt-2 text-[15px] font-bold">{nextComp.name}</p>
          <p className="mt-1 text-[11.5px] text-text-dim">
            Semana {nextComp.week_number} · {nextComp.days} {nextComp.days === 1 ? 'día' : 'días'}
            {nextComp.is_main && <span className="ml-1.5"><Chip color="#fbbf24">Principal</Chip></span>}
          </p>
          <p className="display mt-2 text-2xl font-bold text-amber">
            {nextComp.weeks_away === 0 ? 'Esta semana' : nextComp.weeks_away === 1 ? 'En 1 semana' : `En ${nextComp.weeks_away} semanas`}
          </p>
        </Card>
      )}

      {!simple && (
        <Card title="Fases del macrociclo" className="card-hover">
          <PhaseStrip
            phases={data.phases}
            totalWeeks={data.total_weeks}
            currentWeek={data.is_over ? null : data.current_week}
            competitions={data.competitions}
          />
        </Card>
      )}

      <Card title={vista.tituloTabla(data.current_week ?? '—')} className="card-hover">
        <EstadoTable
          filas={data.statuses}
          muestraColumnaAtleta={vista.muestraColumnaAtleta}
          simple={simple}
        />
      </Card>
    </div>
  )
}
