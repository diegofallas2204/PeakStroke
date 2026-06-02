/**
 * ProgressionChart.tsx — Gráfico de progresión del atleta.
 *
 * Muestra 3 líneas:
 *   - Curva ideal (blanco/gris) — lo planificado desde el inicio
 *   - Curva recalculada (azul) — redistribuida si hay parones
 *   - Puntos reales (verde/rojo) — tiempos ingresados por el entrenador
 *
 * Eje X: fechas DD/MM (no números de semana — regla del proyecto)
 * Eje Y: tiempo en segundos (invertido: más abajo = más rápido)
 */
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'
import type { WeeklyPlan } from '../api'
import { formatTime } from '../utils/timeFormat'

interface Props {
  plans: WeeklyPlan[]
  goalTime: number
  currentTime: number
}

export function ProgressionChart({ plans, goalTime, currentTime }: Props) {
  const data = plans.map(w => ({
    label: format(parseISO(w.week_date), 'dd/MM', { locale: es }),
    week: w.week_number,
    ideal: w.disabled ? null : w.expected_time,
    recalc: w.disabled ? null : (w.expected_time_recalc ?? w.expected_time),
    real: w.real_time ?? null,
  }))

  const yDomain = [
    Math.min(goalTime - 2, ...plans.filter(p => p.real_time).map(p => p.real_time!)) - 1,
    currentTime + 2,
  ]

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    return (
      <div className="bg-slate-800 border border-white/10 rounded-lg p-3 text-xs space-y-1">
        <p className="text-gray-400 font-medium">{label}</p>
        {payload.map((p: any) => (
          <p key={p.dataKey} style={{ color: p.color }}>
            {p.name}: {formatTime(p.value)}
          </p>
        ))}
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="label"
          tick={{ fill: '#94a3b8', fontSize: 11 }}
          tickLine={false}
        />
        <YAxis
          domain={yDomain}
          reversed       // tiempo menor = mejor = más arriba
          tickFormatter={formatTime}
          tick={{ fill: '#94a3b8', fontSize: 11 }}
          tickLine={false}
          width={60}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: '#94a3b8' }}
        />

        {/* Meta */}
        <ReferenceLine y={goalTime} stroke="#fbbf24" strokeDasharray="6 3"
          label={{ value: `Meta: ${formatTime(goalTime)}`, fill: '#fbbf24', fontSize: 11, position: 'insideTopRight' }} />

        {/* Curva ideal */}
        <Line
          type="monotone" dataKey="ideal" name="Plan ideal"
          stroke="#64748b" strokeWidth={2} strokeDasharray="4 2"
          dot={false} connectNulls={false}
        />

        {/* Curva recalculada */}
        <Line
          type="monotone" dataKey="recalc" name="Plan recalculado"
          stroke="#38bdf8" strokeWidth={2}
          dot={false} connectNulls={false}
        />

        {/* Tiempos reales */}
        <Line
          type="monotone" dataKey="real" name="Real"
          stroke="#4ade80" strokeWidth={0}
          dot={{ fill: '#4ade80', r: 5, strokeWidth: 0 }}
          activeDot={{ r: 7 }}
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
