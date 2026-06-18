// Gráfico de parciales del test aeróbico con línea de promedio
// y comparativa contra el test anterior del atleta.
import {
  CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import type { AerobicTest } from '../../lib/types'
import { toClock } from '../../lib/format'
import { ChartTooltip } from '../../components/charts/chartTheme'

export function SplitsChart({ test, previous }: { test: AerobicTest; previous: AerobicTest | null }) {
  const n = Math.max(test.per100_splits.length, previous?.per100_splits.length ?? 0)
  const data = Array.from({ length: n }, (_, i) => ({
    rep: i + 1,
    actual: test.per100_splits[i],
    anterior: previous?.per100_splits[i],
  }))

  const values = data.flatMap((d) => [d.actual, d.anterior]).filter((v): v is number => v != null)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = Math.max((max - min) * 0.2, 0.4)

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
        <CartesianGrid stroke="var(--color-grid)" vertical={false} />
        <XAxis
          dataKey="rep"
          tick={{ fill: 'var(--color-text-dim)', fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace" }}
          tickLine={false} axisLine={false}
          label={{ value: 'Repetición', fill: 'var(--color-text-faint)', fontSize: 10, dy: 12 }}
        />
        <YAxis
          reversed
          domain={[min - pad, max + pad]}
          tickFormatter={(v: number) => toClock(v, 1)}
          tick={{ fill: 'var(--color-text-dim)', fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace" }}
          tickLine={false} axisLine={false} width={52}
        />
        <Tooltip content={<ChartTooltip formatter={(v) => `${toClock(v)} /100m`} />} />
        <ReferenceLine
          y={test.avg_per100} stroke="var(--color-accent)" strokeDasharray="5 4" strokeOpacity={0.9}
          label={{ value: `Promedio ${toClock(test.avg_per100)}`, fill: 'var(--color-accent-soft)', fontSize: 10, position: 'insideTopRight' }}
        />
        {previous && (
          <Line
            type="monotone" dataKey="anterior" name="Test anterior"
            stroke="var(--color-text-faint)" strokeWidth={1.8} strokeDasharray="4 4" dot={false}
          />
        )}
        <Line
          type="monotone" dataKey="actual" name="Test actual"
          stroke="var(--color-cyan)" strokeWidth={2.4}
          dot={{ r: 2.5, fill: 'var(--color-cyan)', strokeWidth: 0 }}
          activeDot={{ r: 4.5, fill: 'var(--color-cyan)', stroke: 'var(--color-surface)', strokeWidth: 2 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
