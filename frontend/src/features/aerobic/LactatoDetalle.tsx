// Ficha de un test de lactato: las cuatro series por repetición (tiempo,
// lactato, FC, brazadas), la tira de esfuerzo y los avisos. Todo lo que se
// enseña viene calculado del backend; aquí solo se pinta.
//
// Un punto con aviso va hueco: «no saques conclusiones de este sin mirarlo».
import {
  CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { AlertTriangle, CheckCircle2, Droplet, Footprints, HeartPulse, Timer, XCircle } from 'lucide-react'
import type { EstadoDeZona, LactateTest, LactateWarning } from '../../lib/types'
import { ZONE_META } from '../../lib/constants'
import { signed, toClock } from '../../lib/format'
import { ChartTooltip } from '../../components/charts/chartTheme'
import { Card, Chip } from '../../components/ui/primitives'

const ESTADO: Record<EstadoDeZona, { texto: string; color: string }> = {
  dentro: { texto: 'En zona', color: '#34d399' },
  debajo: { texto: 'Por debajo', color: '#60a5fa' },
  encima: { texto: 'Por encima', color: '#fb7185' },
}

const TICK = { fill: 'var(--color-text-dim)', fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }

export function LactatoDetalle({ test, menor }: { test: LactateTest; menor: boolean }) {
  const s = test.summary
  const zona = ZONE_META[test.target_zone]
  const dudosos = (campo: LactateWarning['field']) =>
    new Set(test.warnings.filter((w) => w.field === campo).map((w) => w.rep_number))
  const rango = test.zone_range
  const estado = s.lactate_zone ? ESTADO[s.lactate_zone] : null

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Dato titulo="Media" valor={toClock(s.mean_time, 1)} pie={`CV ${s.cv_pct.toFixed(1)} %`} />
        <Dato
          titulo="Vs. propuesto"
          valor={s.diff_proposed != null ? `${signed(s.diff_proposed, 1)} s` : '—'}
          pie={s.pct_reference != null ? `${s.pct_reference.toFixed(1)} % de su mejor marca` : 'Sin marca de referencia'}
        />
        <Dato
          titulo="Lactato"
          valor={s.lactate_median != null ? `${s.lactate_median}` : '—'}
          unidad="mmol/L"
          pie={estado ? <span style={{ color: estado.color }}>{estado.texto} {test.target_zone}</span> : 'Sin muestras'}
        />
        <Dato
          titulo="Estado estable"
          valor={s.steady_state == null ? '—' : s.steady_state
            ? <CheckCircle2 size={22} className="text-mint" aria-label="Sí" />
            : <XCircle size={22} className="text-coral" aria-label="No" />}
          pie={s.second_half_rise != null ? `${signed(s.second_half_rise, 1)} mmol/L en la 2.ª mitad` : 'Faltan muestras'}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-dim">
        <Chip color={zona?.color}>{test.target_zone} · {zona?.label}</Chip>
        {rango && <span>{rango[0]}–{rango[1] ?? '∞'} mmol/L</span>}
        <span>· {test.reps.length}×{test.rep_distance}</span>
        {test.rest_s != null && (
          <span>· {test.rest_type === 'salida' ? 'salida' : 'pausa'} {test.rest_s < 60 ? `${test.rest_s} s` : toClock(test.rest_s, 0)}</span>
        )}
        {test.counted_segment_m && <span>· brazadas en {test.counted_segment_m} m</span>}
        <Protocolo test={test} />
      </div>
      {menor && test.target_zone === 'R1' && (
        <p className="-mt-2 text-[11px] text-text-faint">
          Menor de edad: el techo de R1 es su propio umbral; el rango de adulto es orientativo.
        </p>
      )}

      {test.warnings.length > 0 && (
        <Card className="!border-[rgba(251,191,36,.35)]" title={
          <span className="flex items-center gap-1.5 text-amber"><AlertTriangle size={13} /> Revisar</span>
        }>
          <ul className="flex flex-col gap-1.5 text-[12px]">
            {test.warnings.map((w) => (
              <li key={`${w.rep_number}-${w.field}`} className="flex gap-2">
                <span className="mono shrink-0 text-text-faint">#{w.rep_number}</span>
                <span className="text-text-dim">{w.message}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-4 [&>*]:min-w-0 sm:grid-cols-2">
        <Serie
          titulo="Tiempo" icono={<Timer size={13} />} color="var(--color-cyan)"
          puntos={test.reps.map((r) => ({ rep: r.rep_number, v: r.swim_time }))}
          dudosos={dudosos('tiempo')} formato={(v) => toClock(v, 0)}
          banda={test.proposed_min != null && test.proposed_max != null ? [test.proposed_min, test.proposed_max] : null}
          invertido
        />
        <Serie
          titulo="Lactato · mmol/L" icono={<Droplet size={13} />} color="#fb7185"
          puntos={test.reps.filter((r) => r.lactate != null).map((r) => ({ rep: r.rep_number, v: r.lactate! }))}
          dudosos={dudosos('lactato')} formato={(v) => v.toFixed(1)} n={test.reps.length}
          banda={rango ? [rango[0], rango[1] ?? rango[0] + 4] : null}
        />
        <Serie
          titulo="FC · lat/min" icono={<HeartPulse size={13} />} color="#a78bfa"
          puntos={test.reps.filter((r) => r.heart_rate != null).map((r) => ({ rep: r.rep_number, v: r.heart_rate! }))}
          dudosos={dudosos('fc')} formato={(v) => v.toFixed(0)} n={test.reps.length}
        />
        <Serie
          titulo={`Brazadas por ${test.counted_segment_m ?? '—'} m`} icono={<Footprints size={13} />} color="#34d399"
          puntos={test.reps.filter((r) => r.strokes_mean != null).map((r) => ({ rep: r.rep_number, v: r.strokes_mean! }))}
          dudosos={new Set()} formato={(v) => v.toFixed(1)} n={test.reps.length}
          pie={s.strokes_first != null && s.strokes_last != null
            ? `${s.strokes_first.toFixed(1)} → ${s.strokes_last.toFixed(1)}${s.stroke_drift_pct != null ? ` (${signed(s.stroke_drift_pct, 1)} %)` : ''}${s.stroke_index != null ? ` · índice ${s.stroke_index.toFixed(2)}` : ''}`
            : undefined}
        />
      </div>

      <TiraDeEsfuerzo test={test} />
      {test.notes && <p className="text-[12px] text-text-faint">{test.notes}</p>}
    </div>
  )
}

function Dato({ titulo, valor, unidad, pie }: { titulo: string; valor: React.ReactNode; unidad?: string; pie: React.ReactNode }) {
  return (
    <Card className="card-hover !p-4">
      <p className="card-title">{titulo}</p>
      <p className="display mt-1 flex items-baseline gap-1 text-[22px] font-bold">
        {valor}{unidad && <span className="text-[10.5px] font-normal text-text-faint">{unidad}</span>}
      </p>
      <p className="text-[10.5px] text-text-faint">{pie}</p>
    </Card>
  )
}

function Protocolo({ test }: { test: LactateTest }) {
  const partes = [
    test.sample_site === 'lobulo' ? 'lóbulo' : test.sample_site === 'dedo' ? 'dedo' : null,
    test.analyzer,
    test.sample_minute != null ? `min ${test.sample_minute}` : null,
    test.hr_method === 'palpacion' ? 'FC por palpación' : test.hr_method ? `FC ${test.hr_method === 'banda' ? 'con banda' : 'óptica'}` : null,
  ].filter(Boolean)
  return partes.length ? <span>· {partes.join(' · ')}</span> : null
}

function Serie({
  titulo, icono, color, puntos, dudosos, formato, banda = null, invertido = false, n, pie,
}: {
  titulo: string
  icono: React.ReactNode
  color: string
  puntos: { rep: number; v: number }[]
  dudosos: Set<number>
  formato: (v: number) => string
  banda?: [number, number] | null
  invertido?: boolean
  n?: number
  pie?: string
}) {
  const total = n ?? puntos.length
  const datos = Array.from({ length: total }, (_, i) => ({
    rep: i + 1, v: puntos.find((p) => p.rep === i + 1)?.v,
  }))
  const valores = [...puntos.map((p) => p.v), ...(banda ?? [])]
  const lo = Math.min(...valores)
  const hi = Math.max(...valores)
  const pad = Math.max((hi - lo) * 0.15, 1)
  // Fuera del tiempo, ejes en enteros y desde 0: «2.8 mmol/L» como marca de eje
  // no dice nada, y un lactato o una FC negativos no existen.
  const dominio: [number, number] = invertido
    ? [lo - pad, hi + pad] : [Math.max(0, Math.floor(lo - pad)), Math.ceil(hi + pad)]
  return (
    <Card className="card-hover !p-4" title={<span className="flex items-center gap-1.5" style={{ color }}>{icono} {titulo}</span>}>
      {puntos.length === 0 ? (
        <p className="py-10 text-center text-[12px] text-text-faint">Sin registrar</p>
      ) : (
        <ResponsiveContainer width="100%" height={150}>
          <ComposedChart data={datos} margin={{ top: 4, right: 6, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-grid)" vertical={false} />
            <XAxis dataKey="rep" tick={TICK} tickLine={false} axisLine={false} />
            <YAxis
              domain={dominio} reversed={invertido} allowDecimals={invertido}
              tickFormatter={invertido ? formato : (v: number) => String(v)}
              tick={TICK} tickLine={false} axisLine={false} width={40}
            />
            {banda && <ReferenceArea y1={banda[0]} y2={banda[1]} fill={color} fillOpacity={0.08} strokeOpacity={0} />}
            <Tooltip content={<ChartTooltip formatter={(v) => formato(v)} />} labelFormatter={(r) => `Rep. ${r}`} />
            <Line
              // Recta entre muestras: una curva suavizada inventaría valores
              // entre repeticiones que nadie midió.
              type="linear" dataKey="v" name={titulo} stroke={color} strokeWidth={2} connectNulls
              dot={(p: { cx?: number; cy?: number; payload?: { rep: number; v?: number } }) => {
                if (p.cx == null || p.cy == null || p.payload?.v == null) return <g key={p.payload?.rep} />
                const hueco = dudosos.has(p.payload.rep)
                return (
                  <circle
                    key={p.payload.rep} cx={p.cx} cy={p.cy} r={hueco ? 4.5 : 3}
                    fill={hueco ? 'var(--color-surface)' : color} stroke={color} strokeWidth={hueco ? 2 : 0}
                  />
                )
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
      {pie && <p className="mt-1 text-[11px] text-text-dim">{pie}</p>}
    </Card>
  )
}

function TiraDeEsfuerzo({ test }: { test: LactateTest }) {
  if (!test.reps.some((r) => r.effort != null)) return null
  return (
    <Card className="card-hover !p-4" title="Esfuerzo (CR-10)">
      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${test.reps.length}, minmax(0, 1fr))` }}>
        {test.reps.map((r) => (
          <div key={r.rep_number} className="flex flex-col items-center gap-0.5">
            <span
              className="mono w-full rounded-md py-1.5 text-center text-[11.5px] font-bold"
              style={r.effort == null
                ? { background: 'var(--color-surface-2)', color: 'var(--color-text-faint)' }
                : { background: `rgba(96,165,250,${0.12 + (r.effort / 10) * 0.6})`, color: r.effort >= 7 ? '#fff' : 'var(--color-text)' }}
              title={`Rep. ${r.rep_number}: ${r.effort ?? 'sin registrar'}`}
            >
              {r.effort ?? '—'}
            </span>
            <span className="text-[9px] text-text-faint">{r.rep_number}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
