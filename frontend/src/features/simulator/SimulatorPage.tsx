// Simulador de escenarios: parámetros en vivo contra el motor de predicción,
// con análisis de factibilidad, comparación de curvas y plan resultante.
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FlaskConical, ShieldAlert, ShieldCheck, ShieldX, Waves, Zap } from 'lucide-react'
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../../lib/api'
import { CURVES, CURVE_COLORS, CURVE_LABEL, DISTANCES, SPECIALTIES, STROKES } from '../../lib/constants'
import { toClock, tryToSeconds } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, Field, Spinner } from '../../components/ui/primitives'
import { ChartTooltip } from '../../components/charts/chartTheme'
import { SimZones } from './SimZones'

const FEAS = {
  ok: { icon: ShieldCheck, color: '#34d399' },
  warning: { icon: ShieldAlert, color: '#fbbf24' },
  aggressive: { icon: ShieldX, color: '#fb7185' },
} as const

export function SimulatorPage() {
  const [params, setParams] = useState({
    distance: 100, stroke: 'mariposa', current: '1:07.80', goal: '1:04.50',
    weeks: 12, micro: 4, km: 320, curve: 'sigmoid', specialty: 'velocidad',
  })
  const [debounced, setDebounced] = useState(params)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(params), 300)
    return () => clearTimeout(t)
  }, [params])

  const current = tryToSeconds(debounced.current)
  const goal = tryToSeconds(debounced.goal)
  const valid = current != null && goal != null && goal < current

  const { data, isFetching } = useQuery({
    queryKey: ['sim', debounced],
    queryFn: () => api.simulator.run({
      distance: debounced.distance, stroke: debounced.stroke,
      current_time: current, goal_time: goal,
      total_weeks: debounced.weeks, weeks_per_micro: debounced.micro,
      total_km: debounced.km, curve: debounced.curve, specialty: debounced.specialty,
    }),
    enabled: valid,
    placeholderData: (prev) => prev,
  })

  const set = (key: keyof typeof params, numeric = false) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setParams((p) => ({ ...p, [key]: numeric ? Number(e.target.value) : e.target.value }))

  const ref = usePageEnter([])
  const feasibility = data?.feasibility
  const FeasIcon = feasibility ? FEAS[feasibility.status].icon : FlaskConical
  const feasColor = feasibility ? FEAS[feasibility.status].color : '#8b93b8'

  const chartData = data
    ? data.weeks.map((w, i) => ({
        date_label: w.date_label,
        ...Object.fromEntries(Object.entries(data.curves).map(([name, vals]) => [name, vals[i]])),
      }))
    : []

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Simulador de escenarios"
        subtitle="Modifica semanas, kilómetros y objetivos: el motor recalcula todo en tiempo real, sin tocar los planes guardados"
      />

      <div className="flex flex-col gap-4">
        {/* ── Parámetros (fila superior, a todo el ancho) ── */}
        <Card title="Parámetros del plan" className="card-hover">
          <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-5">
            <Field label="Distancia">
              <select className="field" value={params.distance} onChange={set('distance', true)}>
                {DISTANCES.map((d) => <option key={d} value={d}>{d}m</option>)}
              </select>
            </Field>
            <Field label="Estilo">
              <select className="field" value={params.stroke} onChange={set('stroke')}>
                {STROKES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </Field>
            <Field label="Tiempo actual">
              <input className="field mono" value={params.current} onChange={set('current')} />
            </Field>
            <Field label="Tiempo meta">
              <input className="field mono" value={params.goal} onChange={set('goal')} />
            </Field>
            <Field label="Semanas">
              <input type="number" className="field" value={params.weeks} min={4} max={30} onChange={set('weeks', true)} />
            </Field>
            <Field label="Micro (sem)">
              <select className="field" value={params.micro} onChange={set('micro', true)}>
                <option value={4}>4</option><option value={5}>5</option>
              </select>
            </Field>
            <Field label="Km totales">
              <input type="number" className="field" value={params.km} min={50} max={1500} step={10} onChange={set('km', true)} />
            </Field>
            <Field label="Curva">
              <select className="field" value={params.curve} onChange={set('curve')}>
                {CURVES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </Field>
            <Field label="Especialidad del atleta" className="col-span-2 sm:col-span-1">
              <select className="field" value={params.specialty} onChange={set('specialty')}>
                {SPECIALTIES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </Field>
          </div>
          {!valid && (
            <p className="mt-3 text-[11px] text-coral">
              El tiempo meta debe ser menor al actual (formato m:ss.cc).
            </p>
          )}
        </Card>

        {/* ── Resultados ── */}
        <div className="flex flex-col gap-4">
          {!data && isFetching && <Spinner />}
          {data && feasibility && (
            <>
              <Card className="card-hover glow-edge" animate={false}>
                <div className="flex items-start gap-3.5">
                  <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl"
                    style={{ color: feasColor, background: `${feasColor}16`, border: `1px solid ${feasColor}33` }}>
                    <FeasIcon size={19} />
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2.5">
                      <p className="display text-[14px] font-bold" style={{ color: feasColor }}>
                        {feasibility.status === 'ok' ? 'Objetivo realista'
                          : feasibility.status === 'warning' ? 'Exigente pero posible' : 'Objetivo agresivo'}
                      </p>
                      <span className="flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider text-text-dim">
                        {feasibility.tier === 1 ? <Waves size={10} /> : <Zap size={10} />}
                        Tier {feasibility.tier} · {feasibility.tier === 1 ? 'aeróbico' : 'velocidad'}
                      </span>
                    </div>
                    <p className="mt-1 text-[12px] leading-relaxed text-text-dim">{feasibility.message}</p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-4 gap-3 border-t border-line pt-3.5">
                  <div>
                    <p className="card-title !text-[9px]">Mejora total</p>
                    <p className="mono mt-0.5 text-[15px] font-bold">
                      {feasibility.improvement_total.toFixed(2)}s
                      <span className="ml-1 text-[10px] text-text-faint">
                        ({current ? ((feasibility.improvement_total / current) * 100).toFixed(1) : '—'}%)
                      </span>
                    </p>
                  </div>
                  <div>
                    <p className="card-title !text-[9px]">Requerido / micro</p>
                    <p className="mono mt-0.5 text-[15px] font-bold text-accent-soft">
                      {feasibility.improvement_per_micro.toFixed(3)}s
                    </p>
                  </div>
                  <div>
                    <p className="card-title !text-[9px]">Ventana realista</p>
                    <p className="mono mt-0.5 text-[15px] font-bold text-cyan">
                      {feasibility.window_min != null
                        ? `${feasibility.window_min.toFixed(2)}–${feasibility.window_max.toFixed(2)}s`
                        : `≤ ${feasibility.window_max.toFixed(2)}s`}
                    </p>
                  </div>
                  <div>
                    <p className="card-title !text-[9px]">{feasibility.recommended_weeks ? 'Semanas sugeridas' : 'Tiempo final'}</p>
                    <p className="mono mt-0.5 text-[15px] font-bold" style={{ color: feasibility.recommended_weeks ? 'var(--color-amber)' : 'var(--color-mint)' }}>
                      {feasibility.recommended_weeks ?? toClock(goal ?? 0)}
                    </p>
                  </div>
                </div>
              </Card>

              <Card title="Curvas de progresión comparadas" className="card-hover" animate={false}>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={chartData} margin={{ top: 6, right: 10, left: 4, bottom: 0 }}>
                    <CartesianGrid stroke="var(--color-grid)" vertical={false} />
                    <XAxis dataKey="date_label" tick={{ fill: 'var(--color-text-dim)', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} tickLine={false} axisLine={false} />
                    <YAxis reversed tickFormatter={(v: number) => toClock(v, 1)} domain={['dataMin - 0.4', 'dataMax + 0.4']}
                      tick={{ fill: 'var(--color-text-dim)', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} tickLine={false} axisLine={false} width={50} />
                    <Tooltip content={<ChartTooltip formatter={(v) => toClock(v)} />} />
                    {goal != null && <ReferenceLine y={goal} stroke="var(--color-amber)" strokeDasharray="5 4" strokeOpacity={0.7} />}
                    {Object.keys(data.curves).map((name) => (
                      <Line
                        key={name} type="monotone" dataKey={name} name={CURVE_LABEL[name] ?? name}
                        stroke={CURVE_COLORS[name]}
                        strokeWidth={name === debounced.curve ? 2.8 : 1.4}
                        strokeOpacity={name === debounced.curve ? 1 : 0.45}
                        strokeDasharray={name === debounced.curve ? undefined : '5 4'}
                        dot={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
                <div className="mt-1 flex gap-4 text-[10.5px]">
                  {Object.keys(data.curves).map((name) => (
                    <span key={name} className="flex items-center gap-1.5"
                      style={{ color: name === debounced.curve ? CURVE_COLORS[name] : 'var(--color-text-faint)' }}>
                      <span className="h-0.5 w-4 rounded" style={{ background: CURVE_COLORS[name], opacity: name === debounced.curve ? 1 : 0.4 }} />
                      {CURVE_LABEL[name]}
                    </span>
                  ))}
                </div>
              </Card>

              <SimZones weeks={data.weeks} />

              <Card title="Plan semanal generado" className="card-hover" animate={false} flush>
                <div className="max-h-80 overflow-auto">
                  <table className="tbl">
                    <thead className="sticky top-0 z-10" style={{ background: 'var(--color-surface)' }}>
                      <tr>
                        <th>Semana</th><th>Fase</th><th>Km</th><th>Esperado</th>
                        <th>Pace /100</th><th>R1</th><th>R2</th><th>Mejora</th><th>Acumulada</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.weeks.map((w) => (
                        <tr key={w.week_number}>
                          <td className="mono">S{w.week_number} <span className="text-text-faint">· {w.date_label}</span></td>
                          <td className="text-text-dim">{w.phase}</td>
                          <td className="mono">{w.planned_km}</td>
                          <td className="mono">{toClock(w.expected_time)}</td>
                          <td className="mono font-semibold text-accent-soft">{toClock(w.pace_100m)}</td>
                          <td className="mono text-mint">{w.zones.R1 ? toClock(w.zones.R1.mid, 1) : '—'}</td>
                          <td className="mono text-cyan">{w.zones.R2 ? toClock(w.zones.R2.mid, 1) : '—'}</td>
                          <td className="mono" style={{ color: w.improvement_vs_prev < 0 ? 'var(--color-mint)' : 'var(--color-text-dim)' }}>
                            {w.improvement_vs_prev.toFixed(2)}s
                          </td>
                          <td className="mono text-text-dim">{w.cumulative_improvement.toFixed(2)}s</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
