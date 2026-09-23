// Tabla de plan semana a semana con TODAS las zonas (R1·R2·MVO2·RL·V).
// Reutilizada por el plan principal y por la tabla de semanas de extensión.
import type { SimWeek } from '../../lib/types'
import { ZONE_META, ZONE_ORDER } from '../../lib/constants'
import { toClock } from '../../lib/format'

interface Props {
  weeks: SimWeek[]
  /** Filas de extensión: fondo ámbar tenue para distinguirlas del macro. */
  extension?: boolean
  /** Modo simple: solo lo esencial, sin zonas ni columnas de mejora. */
  simple?: boolean
}

export function SimPlanTable({ weeks, extension = false, simple = false }: Props) {
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
