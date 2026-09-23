// Tooltip compartido de Recharts con la estética del sistema.

interface TooltipEntry {
  dataKey?: string | number
  name?: string | number
  value?: number
  color?: string
}

export function ChartTooltip({
  active, payload, label, formatter,
}: {
  active?: boolean
  payload?: TooltipEntry[]
  label?: string | number
  formatter?: (value: number, name: string) => string
}) {
  if (!active || !payload?.length) return null
  // Filtra entradas no numéricas que Recharts inyecta en Scatter
  // (date_label, week_number, disabled) — sus valores son NaN o boolean.
  const entries = payload.filter(
    (e) => typeof e.value === 'number' && !Number.isNaN(e.value),
  )
  if (!entries.length) return null
  return (
    <div
      className="card !rounded-xl px-3.5 py-2.5 text-xs shadow-2xl"
      style={{ border: '1px solid var(--color-line-strong)' }}
    >
      <p className="mono mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-dim">
        {label}
      </p>
      {entries.map((entry) => (
        <div key={String(entry.dataKey)} className="flex items-center gap-2 py-0.5">
          <span className="size-2 rounded-full" style={{ background: entry.color }} />
          <span className="text-text-dim">{entry.name}:</span>
          <span className="mono font-semibold text-text">
            {formatter
              ? formatter(entry.value as number, String(entry.name))
              : (entry.value as number).toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  )
}
