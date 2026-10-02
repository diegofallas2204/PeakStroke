// La curva de Banister: carga crónica (CTL), aguda (ATL) y su balance (TSB),
// con la carga de cada día (sTSS) de fondo.
//
// Los umbrales de alerta NO se dibujan como líneas: viven solo en el backend
// (`banister.py`) y copiarlos aquí sería la segunda copia de una regla. Lo que
// se pinta es su resultado —el punto del día que avisa— y la franja de
// calentamiento con la fecha que manda el servidor.
import {
  Bar, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { LoadDay, TrainingLoad } from '../../lib/types'
import { LOAD_ALERT_META, LOAD_REASON_LABEL } from '../../lib/constants'
import { toDayMonth, toDDMM } from '../../lib/format'
import { SERIES } from './series'

const AXIS_TICK = { fill: 'var(--color-text-dim)', fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace" }

type Punto = LoadDay & { avisoTsb: number | null }

export function LoadChart({ load }: { load: TrainingLoad }) {
  const data: Punto[] = load.days.map((d) => ({ ...d, avisoTsb: d.alert ? d.tsb : null }))
  const first = data[0]?.date
  const last = data[data.length - 1]?.date
  // La franja va del inicio de la historia al primer día con alertas, recortada
  // al rango visible. Si el rango empieza después, no hay franja.
  const bandFrom = load.history_start && first && load.history_start > first ? load.history_start : first
  const bandTo = load.warmup_until && last && load.warmup_until < last ? load.warmup_until : last
  const showBand = !!(load.warmup_until && bandFrom && bandTo && bandFrom < bandTo
    && load.warmup_until > (first ?? ''))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--color-grid)" vertical={false} />
        <XAxis
          dataKey="date" tickFormatter={toDDMM} minTickGap={28}
          tick={AXIS_TICK} tickLine={false} axisLine={false}
        />
        <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={40} />
        <Tooltip content={<LoadTooltip />} />
        {showBand && (
          <ReferenceArea
            x1={bandFrom} x2={bandTo} fill="var(--color-text-faint)" fillOpacity={0.08}
            label={{ value: 'Calentamiento · sin alertas', fill: 'var(--color-text-faint)', fontSize: 10, position: 'insideTopLeft' }}
          />
        )}
        <ReferenceLine y={0} stroke="var(--color-line-strong)" />
        <Bar dataKey="stss" name={SERIES.stss.label} fill={SERIES.stss.color} fillOpacity={0.35} barSize={4} />
        <Line type="monotone" dataKey="ctl" name={SERIES.ctl.label} stroke={SERIES.ctl.color} strokeWidth={2.4} dot={false} />
        <Line type="monotone" dataKey="atl" name={SERIES.atl.label} stroke={SERIES.atl.color} strokeWidth={1.8} dot={false} />
        <Line type="monotone" dataKey="tsb" name={SERIES.tsb.label} stroke={SERIES.tsb.color} strokeWidth={2} strokeDasharray="5 3" dot={false} />
        {/* Los días que avisan, sobre la línea del balance y del color de su nivel. */}
        <Line
          dataKey="avisoTsb" stroke="transparent" legendType="none" isAnimationActive={false}
          activeDot={false}
          dot={(props: { cx?: number; cy?: number; payload?: Punto; index?: number }) => {
            const { cx, cy, payload, index } = props
            if (cx == null || cy == null || !payload?.alert) return <g key={`aviso-${index}`} />
            return (
              <circle
                key={`aviso-${index}`} cx={cx} cy={cy} r={3.5}
                fill={LOAD_ALERT_META[payload.alert].color} stroke="var(--color-surface)" strokeWidth={1.5}
              />
            )
          }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function LoadTooltip({ active, payload }: { active?: boolean; payload?: { payload: Punto }[] }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const rows: [keyof typeof SERIES, number][] = [['stss', d.stss], ['ctl', d.ctl], ['atl', d.atl], ['tsb', d.tsb]]
  return (
    <div className="card !rounded-xl px-3.5 py-2.5 text-xs shadow-2xl" style={{ border: '1px solid var(--color-line-strong)' }}>
      <p className="mono mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-dim">{toDayMonth(d.date)}</p>
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-center gap-2 py-0.5">
          <span className="size-2 rounded-full" style={{ background: SERIES[k].color }} />
          <span className="text-text-dim">{SERIES[k].label}:</span>
          <span className="mono font-semibold text-text">{v.toFixed(1)}</span>
        </div>
      ))}
      {d.alert && (
        <p className="mt-1.5 border-t border-line pt-1.5 font-semibold" style={{ color: LOAD_ALERT_META[d.alert].color }}>
          {LOAD_ALERT_META[d.alert].label}: {d.reasons.map((r) => LOAD_REASON_LABEL[r] ?? r).join(' · ')}
        </p>
      )}
    </div>
  )
}
