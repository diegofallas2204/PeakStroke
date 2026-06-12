// Gráfico de progresión de un evento: curva ideal, curva recalculada
// (proyección punteada desde el último real) y puntos reales.
// Eje Y invertido: menor tiempo = más arriba. Eje X: fechas DD/MM.
import {
  CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer,
  Scatter, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { Week } from '../../lib/types'
import { toClock } from '../../lib/format'
import { ChartTooltip } from './chartTheme'

export function ProgressionChart({
  weeks, goalTime, height = 280, currentWeek,
}: { weeks: Week[]; goalTime: number; height?: number; currentWeek?: number | null }) {
  const data = weeks.map((w) => ({
    date_label: w.date_label,
    week_number: w.week_number,
    ideal: w.expected_time,
    recalc: w.recalc_time,
    real: w.real_time,
    disabled: w.disabled,
  }))

  const allTimes = data.flatMap((d) => [d.ideal, d.recalc ?? undefined, d.real ?? undefined])
    .filter((v): v is number => v != null)
  const min = Math.min(...allTimes, goalTime)
  const max = Math.max(...allTimes, goalTime)
  const pad = Math.max((max - min) * 0.12, 0.4)

  const currentLabel = currentWeek
    ? data.find((d) => d.week_number === currentWeek)?.date_label
    : undefined

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid stroke="rgba(148,163,224,.06)" vertical={false} />
        <XAxis
          dataKey="date_label"
          tick={{ fill: '#8b93b8', fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace" }}
          tickLine={false} axisLine={false}
        />
        <YAxis
          reversed
          domain={[min - pad, max + pad]}
          tickFormatter={(v: number) => toClock(v, 1)}
          tick={{ fill: '#8b93b8', fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace" }}
          tickLine={false} axisLine={false} width={52}
        />
        <Tooltip content={<ChartTooltip formatter={(v) => toClock(v)} />} />
        <ReferenceLine
          y={goalTime} stroke="#fbbf24" strokeDasharray="5 4" strokeOpacity={0.8}
          label={{ value: `Meta ${toClock(goalTime)}`, fill: '#fbbf24', fontSize: 10, position: 'insideBottomRight' }}
        />
        {currentLabel && (
          <ReferenceLine x={currentLabel} stroke="#8b93b8" strokeDasharray="3 4" strokeOpacity={0.5}
            label={{ value: 'Hoy', fill: '#8b93b8', fontSize: 9.5, position: 'top' }} />
        )}
        <Line
          type="monotone" dataKey="ideal" name="Plan ideal"
          stroke="#8b5cf6" strokeWidth={2} dot={false}
          strokeOpacity={0.85}
        />
        <Line
          type="monotone" dataKey="recalc" name="Proyección ajustada"
          stroke="#22d3ee" strokeWidth={2.2} strokeDasharray="6 4"
          dot={false} connectNulls
        />
        <Scatter dataKey="real" name="Tiempo real" fill="#34d399" shape={(props: { cx?: number; cy?: number }) => (
          props.cx != null && props.cy != null
            ? <circle cx={props.cx} cy={props.cy} r={4} fill="#34d399" stroke="#06070b" strokeWidth={1.5} style={{ filter: 'drop-shadow(0 0 5px rgba(52,211,153,.8))' }} />
            : <g />
        )} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
