// Simulador de escenarios: parámetros en vivo contra el motor de predicción,
// con análisis de factibilidad, comparación de curvas y plan resultante.
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CalendarClock, FlaskConical, Repeat2, ShieldAlert, ShieldCheck, ShieldX, Waves, Zap } from 'lucide-react'
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../../lib/api'
import {
  CURVES, CURVE_COLORS, CURVE_LABEL, DISTANCES, POOLS, SPECIALTIES,
  ZONE_META, ZONE_ORDER, coerceStroke, specialtyForDistance, strokeOptionsForDistance,
} from '../../lib/constants'
import type { SimWeek } from '../../lib/types'
import { toClock, tryToSeconds } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { useSimpleMode } from '../../hooks/useSimpleMode'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, Field, Spinner } from '../../components/ui/primitives'
import { ChartTooltip } from '../../components/charts/chartTheme'
import { weekDateTick } from '../../components/charts/weekAxisTick'
import { SimZones } from './SimZones'

const FEAS = {
  ok: { icon: ShieldCheck, color: '#34d399' },
  warning: { icon: ShieldAlert, color: '#fbbf24' },
  aggressive: { icon: ShieldX, color: '#fb7185' },
} as const

const SEASON_VERDICT: Record<string, { color: string; label: string }> = {
  ok: { color: '#34d399', label: 'Realista' },
  optimistic: { color: '#fbbf24', label: 'Optimista · techo' },
  unrealistic: { color: '#fb7185', label: 'Poco realista' },
}

// Tabla de plan semana a semana con TODAS las zonas (R1·R2·MVO2·RL·V).
// Reutilizada por el plan principal y por la tabla de semanas de extensión.
function PlanTable({ weeks, extension = false, simple = false }: { weeks: SimWeek[]; extension?: boolean; simple?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="tbl">
        <thead>
          <tr>
            <th>Semana</th><th>Fase</th><th>Km</th><th>Esperado</th><th>Pace /100</th>
            {!simple && ZONE_ORDER.map((z) => (
              <th key={z} style={{ color: ZONE_META[z].color }}>{z}</th>
            ))}
            {!simple && <th>Mejora</th>}
            {!simple && <th>Acumulada</th>}
          </tr>
        </thead>
        <tbody>
          {weeks.map((w) => (
            <tr key={w.week_number} style={extension ? { background: 'rgba(251,191,36,.05)' } : undefined}>
              <td className="mono">
                S{w.week_number} <span className="text-text-faint">· {w.date_label}</span>
              </td>
              <td className="text-text-dim">{w.phase}</td>
              <td className="mono">{w.planned_km}</td>
              <td className="mono">{toClock(w.expected_time)}</td>
              <td className="mono font-semibold text-accent-soft">{toClock(w.pace_100m)}</td>
              {!simple && ZONE_ORDER.map((z) => (
                <td key={z} className="mono text-[11.5px]" style={{ color: ZONE_META[z].color }}>
                  {w.zones[z] ? toClock(w.zones[z]!.mid, 1) : '—'}
                </td>
              ))}
              {!simple && (
                <td className="mono" style={{ color: w.improvement_vs_prev < 0 ? 'var(--color-mint)' : 'var(--color-text-dim)' }}>
                  {w.improvement_vs_prev.toFixed(2)}s
                </td>
              )}
              {!simple && (
                <td className="mono text-text-dim">{w.cumulative_improvement.toFixed(2)}s</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SimulatorPage() {
  const [params, setParams] = useState({
    distance: 100, stroke: 'mariposa', current: '1:07.80', goal: '1:04.50',
    weeks: 12, micro: 4, km: 320, curve: 'science', pool: '50', specialty: 'velocidad',
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
      total_km: debounced.km, curve: debounced.curve, pool: debounced.pool,
      specialty: debounced.specialty,
    }),
    enabled: valid,
    placeholderData: (prev) => prev,
  })

  // Proyección ANUAL: temporada = 3 macrociclos encadenados (motor de dominio).
  // Solo depende del tiempo actual y la prueba (no de la meta ni las semanas).
  const { data: season } = useQuery({
    queryKey: ['season', debounced.distance, debounced.stroke, current, debounced.pool],
    queryFn: () => api.simulator.season({
      distance: debounced.distance, stroke: debounced.stroke,
      current_time: current, pool: debounced.pool, n_macros: 3,
    }),
    enabled: current != null,
    placeholderData: (prev) => prev,
  })

  const set = (key: keyof typeof params, numeric = false) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setParams((p) => ({ ...p, [key]: numeric ? Number(e.target.value) : e.target.value }))

  const [simple] = useSimpleMode()
  const ref = usePageEnter([])
  const feasibility = data?.feasibility
  const FeasIcon = feasibility ? FEAS[feasibility.status].icon : FlaskConical
  const feasColor = feasibility ? FEAS[feasibility.status].color : '#8b93b8'

  // Gráfico = macro + extensión, para ver la proyección COMPLETA hasta la meta
  // (si la meta supera el techo, el macro cierra en el techo realista y la
  // extensión continúa al ritmo seguro hasta la meta; así no queda recortada).
  const lastMacroIdx = data ? data.weeks.length - 1 : -1
  const hasExt = !!data && data.extension_weeks.length > 0
  const macroEndLabel = data?.weeks.length ? data.weeks[lastMacroIdx].date_label : null
  // El tramo de extensión va en su PROPIA serie (`ext`) para pintarlo distinto
  // (punteado ámbar). En las filas del macro `ext` es null salvo en la última,
  // donde toma el valor de cierre del macro para CONECTAR con la extensión.
  const chartData = data
    ? [
        ...data.weeks.map((w, i) => ({
          date_label: w.date_label, week_number: w.week_number,
          ...Object.fromEntries(Object.entries(data.curves).map(([name, vals]) => [name, vals[i]])),
          ext: i === lastMacroIdx && hasExt ? data.curves[debounced.curve]?.[lastMacroIdx] ?? null : null,
        })),
        ...data.extension_weeks.map((w) => ({
          date_label: w.date_label, week_number: w.week_number,
          ext: w.expected_time,   // continuación realista hasta la meta (común a todas las curvas)
        })),
      ]
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
              <select className="field" value={params.distance}
                onChange={(e) => {
                  const distance = Number(e.target.value)
                  // Autocorrige el estilo si la distancia lo invalida (p. ej. 400 mariposa → libre)
                  // y autoselecciona la especialidad sugerida por la prueba (el coach puede cambiarla).
                  setParams((p) => ({
                    ...p, distance,
                    stroke: coerceStroke(distance, p.stroke),
                    specialty: specialtyForDistance(distance),
                  }))
                }}>
                {DISTANCES.map((d) => <option key={d} value={d}>{d}m</option>)}
              </select>
            </Field>
            <Field label="Estilo">
              <select className="field" value={params.stroke} onChange={set('stroke')}>
                {strokeOptionsForDistance(params.distance).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
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
            <Field label="Piscina">
              <select className="field" value={params.pool} onChange={set('pool')}>
                {POOLS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </Field>
            <Field label="Especialidad (auto)" className="col-span-2 sm:col-span-1">
              <select className="field" value={params.specialty} onChange={set('specialty')}
                title="Sugerida por la distancia de la prueba — puedes cambiarla.">
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
                {!simple && (
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
                )}
              </Card>

              {/* ── Proyección ANUAL: temporada = 3 macrociclos encadenados ── */}
              {!simple && season && (() => {
                const v = SEASON_VERDICT[season.verdict] ?? SEASON_VERDICT.ok
                return (
                  <Card title="Proyección anual · temporada de 3 macrociclos" className="card-hover" animate={false}>
                    <div className="flex items-start gap-3.5">
                      <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl"
                        style={{ color: v.color, background: `${v.color}16`, border: `1px solid ${v.color}33` }}>
                        <CalendarClock size={19} />
                      </span>
                      <div className="flex-1">
                        <div className="flex items-center gap-2.5">
                          <p className="display text-[14px] font-bold" style={{ color: v.color }}>
                            Temporada: −{season.season_improvement_pct.toFixed(2)}%
                          </p>
                          <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider"
                            style={{ color: v.color }}>{v.label}</span>
                          <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider text-text-dim">
                            nivel {season.level}
                          </span>
                        </div>
                        <p className="mt-1 text-[12px] leading-relaxed text-text-dim">{season.message}</p>
                        <p className="mt-0.5 text-[11px] text-text-faint">
                          Techo típico de la literatura para {season.level}:{' '}
                          <span className="mono">{season.annual_low_pct}–{season.annual_high_pct}%</span> anual ·
                          de <span className="mono text-text-dim">{toClock(season.season_start)}</span> a{' '}
                          <span className="mono text-text-dim">{toClock(season.season_end)}</span>
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-3 border-t border-line pt-3.5">
                      {season.macros.map((m) => (
                        <div key={m.n_mac}>
                          <p className="card-title !text-[9px]">Macro {m.n_mac}</p>
                          <p className="mono mt-0.5 text-[15px] font-bold" style={{ color: v.color }}>
                            −{m.improvement_pct.toFixed(2)}%
                          </p>
                          <p className="mono text-[10px] text-text-faint">
                            {toClock(m.start_time)} → {toClock(m.end_time)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </Card>
                )
              })()}

              {/* Aviso de semanas extra: solo en modo completo */}
              {!simple && feasibility.recommended_weeks != null && (
                <Card title="Semanas adicionales estimadas" className="card-hover" animate={false}>
                  <div className="flex items-start gap-3.5">
                    <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl"
                      style={{ color: '#fbbf24', background: '#fbbf2416', border: '1px solid #fbbf2433' }}>
                      <CalendarClock size={17} />
                    </span>
                    <div className="flex-1">
                      <p className="text-[12px] leading-relaxed text-text-dim">
                        La meta supera el techo realista en {debounced.weeks} semanas. El motor estima
                        cuántas necesitarías y detalla cada una en la <span className="font-semibold text-text">tabla de extensión</span> de abajo
                        — <span className="font-semibold text-text">no modifica tu plan ni ningún cálculo</span>.
                      </p>
                      <table className="tbl mt-3">
                        <tbody>
                          <tr>
                            <td className="text-text-dim">Semanas del plan actual</td>
                            <td className="mono text-right">{debounced.weeks}</td>
                          </tr>
                          <tr>
                            <td className="text-text-dim">Semanas estimadas para la meta</td>
                            <td className="mono text-right">{feasibility.recommended_weeks}</td>
                          </tr>
                          <tr>
                            <td className="font-semibold">Semanas extra (tabla de extensión)</td>
                            <td className="mono text-right font-bold" style={{ color: '#fbbf24' }}>
                              +{feasibility.extension_weeks ?? Math.max(0, (feasibility.recommended_weeks ?? debounced.weeks) - debounced.weeks)}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </Card>
              )}

              {!simple && (
                <Card title={`Curva de progresión · ${CURVE_LABEL[debounced.curve] ?? debounced.curve}`} className="card-hover" animate={false}>
                  <ResponsiveContainer width="100%" height={262}>
                    <LineChart data={chartData} margin={{ top: 6, right: 14, left: 4, bottom: 4 }}>
                      <CartesianGrid stroke="var(--color-grid)" vertical={false} />
                      <XAxis dataKey="date_label" interval="preserveStartEnd" minTickGap={16}
                        height={34} tick={weekDateTick(chartData)} tickLine={false} axisLine={false} />
                      <YAxis reversed tickFormatter={(v: number) => toClock(v, 1)} domain={['dataMin - 0.3', 'dataMax + 0.3']}
                        tick={{ fill: 'var(--color-text-dim)', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} tickLine={false} axisLine={false} width={50} />
                      <Tooltip content={<ChartTooltip formatter={(v) => toClock(v)} />} />
                      {goal != null && (
                        <ReferenceLine y={goal} stroke="var(--color-amber)" strokeDasharray="5 4" strokeOpacity={0.7}
                          label={{ value: `Meta ${toClock(goal)}`, fill: 'var(--color-amber)', fontSize: 9.5, position: 'insideBottomRight' }} />
                      )}
                      {/* Techo realista I_max: donde cierra el macro (la meta agresiva sigue en la extensión). */}
                      <ReferenceLine y={feasibility.realistic_ceiling} stroke="var(--color-cyan)" strokeDasharray="2 4" strokeOpacity={0.55}
                        label={{ value: 'Techo realista', fill: 'var(--color-cyan)', fontSize: 9.5, position: 'insideTopRight' }} />
                      {/* Frontera macro → extensión: a partir de aquí es la continuación realista hasta la meta. */}
                      {hasExt && macroEndLabel && (
                        <ReferenceLine x={macroEndLabel} stroke="var(--color-amber)" strokeDasharray="3 4" strokeOpacity={0.6}
                          label={{ value: 'fin del macro', fill: 'var(--color-amber)', fontSize: 9, position: 'insideTopLeft' }} />
                      )}
                      {/* Curva científica como referencia tenue cuando se eligió otra función. */}
                      {debounced.curve !== 'science' && (
                        <Line type="monotone" dataKey="science" name="Científica (referencia)"
                          stroke={CURVE_COLORS.science} strokeWidth={1.4} strokeOpacity={0.4}
                          strokeDasharray="5 4" dot={false} connectNulls={false} />
                      )}
                      {/* Función elegida = protagonista (se redibuja al cambiar el selector). */}
                      <Line type="monotone" dataKey={debounced.curve} name={CURVE_LABEL[debounced.curve] ?? debounced.curve}
                        stroke={CURVE_COLORS[debounced.curve]} strokeWidth={2.8} dot={false} connectNulls={false} />
                      {/* Semanas de EXTENSIÓN: tramo punteado ámbar, continuación realista hasta la meta. */}
                      <Line type="monotone" dataKey="ext" name="Extensión → meta"
                        stroke="var(--color-amber)" strokeWidth={2.2} strokeDasharray="6 4"
                        dot={false} connectNulls={false} />
                    </LineChart>
                  </ResponsiveContainer>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10.5px] text-text-faint">
                    <span className="flex items-center gap-1.5">
                      <span className="h-[3px] w-5 rounded" style={{ background: CURVE_COLORS[debounced.curve] }} />
                      {CURVE_LABEL[debounced.curve]} · macro
                    </span>
                    {hasExt && (
                      <span className="flex items-center gap-1.5">
                        <span className="w-5 border-t-2 border-dashed" style={{ borderColor: 'var(--color-amber)' }} />
                        Extensión → meta
                      </span>
                    )}
                    {debounced.curve !== 'science' && (
                      <span className="flex items-center gap-1.5">
                        <span className="w-5 border-t-2 border-dashed" style={{ borderColor: CURVE_COLORS.science, opacity: 0.5 }} />
                        Científica (ref.)
                      </span>
                    )}
                  </div>
                  <p className="mt-1.5 text-[10.5px] leading-relaxed text-text-faint">
                    La función define la forma de la progresión, acotada por el techo científico I_max.
                    {hasExt
                      ? ' La meta supera el techo del macro: la curva (sólida) cierra en el techo realista y la extensión (ámbar punteada) continúa hasta la meta proyectada.'
                      : ' La meta cabe dentro del techo, así que la curva la alcanza dentro del macro.'}
                  </p>
                </Card>
              )}

              {!simple && <SimZones weeks={data.weeks} />}

              <Card title={`Plan semanal generado · ${data.weeks.length} semanas`} className="card-hover" animate={false} flush>
                <PlanTable weeks={data.weeks} simple={simple} />
                {!simple && (
                  <p className="border-t border-line px-4 py-2.5 text-[10px] text-text-faint">
                    Tiempo por zona = punto medio del rango (pace /100m sobre el tiempo esperado de la semana).
                  </p>
                )}
              </Card>

              {/* Tabla de EXTENSIÓN: solo en modo completo */}
              {!simple && data.extension_weeks.length > 0 && (
                <Card
                  title={`Semanas de extensión · +${data.extension_weeks.length} (continuación realista hasta la meta)`}
                  className="card-hover" animate={false} flush
                >
                  <div className="flex items-center gap-2.5 px-4 pt-3.5">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-lg"
                      style={{ color: '#fbbf24', background: '#fbbf2416', border: '1px solid #fbbf2433' }}>
                      <Repeat2 size={14} />
                    </span>
                    <p className="text-[11.5px] leading-relaxed text-text-dim">
                      El macro de {debounced.weeks} sem cierra en el techo realista
                      (<span className="mono font-semibold text-text">{toClock(data.feasibility.realistic_ceiling)}</span>);
                      estas semanas continúan al ritmo seguro hasta la meta. Total estimado:{' '}
                      <span className="font-semibold" style={{ color: '#fbbf24' }}>{data.feasibility.recommended_weeks} semanas</span>.
                    </p>
                  </div>
                  <div className="mt-2.5">
                    <PlanTable weeks={data.extension_weeks} extension />
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
