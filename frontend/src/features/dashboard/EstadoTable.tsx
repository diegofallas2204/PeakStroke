// La tabla de estado por prueba del dashboard.
//
// Extraída de `DashboardPage` con la vista de atleta: la columna "Atleta"
// repetiría el mismo nombre en todas las filas cuando quien mira es el propio
// atleta, y una columna que siempre dice lo mismo es ruido que ocupa ancho.
import type { AthleteStatusRow } from '../../lib/types'
import { SPECIALTY_LABEL } from '../../lib/constants'
import { signed, toClock } from '../../lib/format'
import { StatusBadge } from '../../components/ui/primitives'

export function EstadoTable({
  filas, muestraColumnaAtleta, simple,
}: { filas: AthleteStatusRow[]; muestraColumnaAtleta: boolean; simple: boolean }) {
  return (
    <table className="tbl">
      <thead>
        <tr>
          {muestraColumnaAtleta && <th>Atleta</th>}
          {!simple && <th>Especialidad</th>}
          <th>Prueba</th>
          <th>Esperado</th><th>Real</th><th>Diferencia</th>
          {!simple && <th>Progreso a meta</th>}
          <th>Estado</th>
        </tr>
      </thead>
      <tbody>
        {filas.map((row) => (
          <tr key={row.event_id}>
            {muestraColumnaAtleta && <td className="font-semibold">{row.name}</td>}
            {!simple && (
              <td className="text-text-dim">{SPECIALTY_LABEL[row.specialty] ?? row.specialty}</td>
            )}
            <td className={muestraColumnaAtleta ? 'text-text-dim' : 'font-semibold'}>
              {row.event_label}
            </td>
            <td className="mono">{toClock(row.expected_time)}</td>
            <td className="mono font-semibold">{toClock(row.real_time)}</td>
            <td
              className="mono"
              style={{
                color: row.diff_seconds == null
                  ? 'var(--color-text-faint)'
                  : row.diff_seconds <= 0 ? 'var(--color-mint)' : 'var(--color-coral)',
              }}
            >
              {row.diff_seconds != null ? `${signed(row.diff_seconds)}s` : '—'}
            </td>
            {!simple && (
              <td>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-3">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${Math.min(row.progress_percent, 100)}%`,
                        background: 'linear-gradient(90deg,var(--color-accent),var(--color-cyan))',
                      }}
                    />
                  </div>
                  <span className="mono text-[10.5px] text-text-dim">
                    {row.progress_percent.toFixed(0)}%
                  </span>
                </div>
              </td>
            )}
            <td><StatusBadge status={row.status} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
