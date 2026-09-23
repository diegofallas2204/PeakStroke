// Curva de progresión del simulador. El gráfico pinta macro + extensión juntos
// para ver la proyección COMPLETA hasta la meta: si la meta supera el techo, el
// macro cierra en el techo realista y la extensión continúa al ritmo seguro.
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import type { SimulationResult } from '../../lib/types'
import { CURVE_COLORS, CURVE_LABEL } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'
import { ChartTooltip } from '../../components/charts/chartTheme'
import { weekDateTick } from '../../components/charts/weekAxisTick'

interface Props {
  data: SimulationResult
  /** Función de progresión elegida en los parámetros (la protagonista del gráfico). */
  curve: string
  goal: number | null
}

export function SimCurveChart({ data, curve, goal }: Props) {
  const lastMacroIdx = data.weeks.length - 1
  const hasExt = data.extension_weeks.length > 0
  const macroEndLabel = data.weeks.length ? data.weeks[lastMacroIdx].date_label : null

  // El tramo de extensión va en su PROPIA serie (`ext`) para pintarlo distinto
  // (punteado ámbar). En las filas del macro `ext` es null salvo en la última,
  // donde toma el valor de cierre del macro para CONECTAR con la extensión.
  const chartData = [
    ...data.weeks.map((w, i) => ({
      date_label: w.date_label, week_number: w.week_number,
      ...Object.fromEntries(Object.entries(data.curves).map(([name, vals]) => [name, vals[i]])),
      ext: i === lastMacroIdx && hasExt ? data.curves[curve]?.[lastMacroIdx] ?? null : null,
    })),
    ...data.extension_weeks.map((w) => ({
      date_label: w.date_label, week_number: w.week_number,
      ext: w.expected_time,   // continuación realista hasta la meta (común a todas las curvas)
    })),
  ]

  return (
    <Card title={`Curva de progresión · ${CURVE_LABEL[curve] ?? curve}`} className="card-hover" animate={false}>
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
          <ReferenceLine y={data.feasibility.realistic_ceiling} stroke="var(--color-cyan)" strokeDasharray="2 4" strokeOpacity={0.55}
            label={{ value: 'Techo realista', fill: 'var(--color-cyan)', fontSize: 9.5, position: 'insideTopRight' }} />
          {/* Frontera macro → extensión: a partir de aquí es la continuación realista hasta la meta. */}
          {hasExt && macroEndLabel && (
            <ReferenceLine x={macroEndLabel} stroke="var(--color-amber)" strokeDasharray="3 4" strokeOpacity={0.6}
              label={{ value: 'fin del macro', fill: 'var(--color-amber)', fontSize: 9, position: 'insideTopLeft' }} />
          )}
          {/* Curva científica como referencia tenue cuando se eligió otra función. */}
          {curve !== 'science' && (
            <Line type="monotone" dataKey="science" name="Científica (referencia)"
              stroke={CURVE_COLORS.science} strokeWidth={1.4} strokeOpacity={0.4}
              strokeDasharray="5 4" dot={false} connectNulls={false} />
          )}
          {/* Función elegida = protagonista (se redibuja al cambiar el selector). */}
          <Line type="monotone" dataKey={curve} name={CURVE_LABEL[curve] ?? curve}
            stroke={CURVE_COLORS[curve]} strokeWidth={2.8} dot={false} connectNulls={false} />
          {/* Semanas de EXTENSIÓN: tramo punteado ámbar, continuación realista hasta la meta. */}
          <Line type="monotone" dataKey="ext" name="Extensión → meta"
            stroke="var(--color-amber)" strokeWidth={2.2} strokeDasharray="6 4"
            dot={false} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10.5px] text-text-faint">
        <span className="flex items-center gap-1.5">
          <span className="h-[3px] w-5 rounded" style={{ background: CURVE_COLORS[curve] }} />
          {CURVE_LABEL[curve]} · macro
        </span>
        {hasExt && (
          <span className="flex items-center gap-1.5">
            <span className="w-5 border-t-2 border-dashed" style={{ borderColor: 'var(--color-amber)' }} />
            Extensión → meta
          </span>
        )}
        {curve !== 'science' && (
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
  )
}
