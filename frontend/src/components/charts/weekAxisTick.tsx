// Tick de eje X en dos líneas: número de semana (S#) arriba, fecha DD/MM abajo.
// Compartido por todos los gráficos con eje temporal (simulador, plan semanal,
// comparación, dashboard, tabla del equipo). Recibe las filas del gráfico para
// resolver semana/fecha por índice (el tick solo conoce su posición en el eje).
type WeekRow = { week_number?: number; date_label?: string }

export function weekDateTick(rows: WeekRow[]) {
  return (props: { x?: number | string; y?: number | string; payload?: { index: number } }) => {
    const { x = 0, y = 0, payload } = props
    const row = rows[payload?.index ?? -1]
    if (!row) return <g />
    const hasWeek = row.week_number != null
    return (
      <g transform={`translate(${x},${y})`}>
        {hasWeek && (
          <text x={0} y={0} dy={11} textAnchor="middle" fontFamily="'JetBrains Mono', monospace"
            fontSize={11} fontWeight={600} fill="var(--color-text-dim)">
            S{row.week_number}
          </text>
        )}
        <text x={0} y={0} dy={hasWeek ? 24 : 12} textAnchor="middle" fontFamily="'JetBrains Mono', monospace"
          fontSize={10} fill="var(--color-text-faint)">
          {row.date_label}
        </text>
      </g>
    )
  }
}
