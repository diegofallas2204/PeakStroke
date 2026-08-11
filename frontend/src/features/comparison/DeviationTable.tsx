// Desviación semana a semana, en tabla.
//
// Antes era un gráfico de barras. Un desvío es un número con signo que se lee
// contra otro número —"1:05.20 donde tocaba 1:04.80, cuatro décimas tarde"— y
// la barra obligaba a estimar la altura y a pasar el ratón por encima para
// recuperar el dato exacto. La tabla lo dice y encima cabe el tiempo planificado
// al lado, que es la referencia que da sentido al desvío.
//
// La barra no desaparece del todo: sobrevive dentro de la celda, alineada al
// cero, para que la forma de la deriva siga leyéndose de un vistazo.
import type { Week } from '../../lib/types'
import { toClock, signed } from '../../lib/format'
import { Card, StatusBadge } from '../../components/ui/primitives'

const MEJOR = '#34d399'
const PEOR = '#fb7185'

export function DeviationTable({ weeks }: { weeks: Week[] }) {
  // Escala común a todas las filas: la barra de una semana solo significa algo
  // comparada con las demás. Suelo de 0.5 s para que un desvío diminuto no se
  // dibuje a pantalla completa por ser el mayor de una lista de desvíos nimios.
  const peak = Math.max(0.5, ...weeks.map((w) => Math.abs(w.diff_seconds ?? 0)))

  return (
    <Card title="Desviación semanal · real vs. plan" className="card-hover" flush>
      <div className="overflow-x-auto">
        <table className="tbl">
          <thead>
            <tr>
              <th>Semana</th>
              <th>Planificado</th>
              <th>Real</th>
              <th>Desvío</th>
              <th className="w-[30%]">Deriva</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {weeks.map((week) => {
              const diff = week.diff_seconds ?? 0
              const mejor = diff <= 0
              const color = mejor ? MEJOR : PEOR
              return (
                <tr key={week.id}>
                  <td>
                    <span className="mono font-semibold">S{week.week_number}</span>
                    <span className="ml-2 text-[11px] text-text-faint">{week.date_label}</span>
                  </td>
                  <td className="mono text-text-dim">
                    {toClock(week.recalc_time ?? week.expected_time)}
                  </td>
                  <td className="mono font-semibold">{toClock(week.real_time)}</td>
                  <td className="mono font-semibold" style={{ color }}>
                    {signed(diff)}s
                    {week.diff_percent != null && (
                      <span className="ml-1.5 text-[10.5px] font-normal opacity-70">
                        {signed(week.diff_percent, 1)}%
                      </span>
                    )}
                  </td>
                  <td>
                    <DeriveBar diff={diff} peak={peak} color={color} mejor={mejor} />
                  </td>
                  <td><StatusBadge status={week.status} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-4 py-2.5 text-[10px] text-text-faint">
        Desvío negativo = más rápido que el plan. La columna «Planificado» usa la
        curva recalculada cuando existe, que es contra la que se juzga la semana.
      </p>
    </Card>
  )
}

/**
 * Media barra a cada lado de un cero fijo al centro.
 *
 * Un desvío tiene signo, así que una barra que siempre crece hacia la derecha
 * mentiría sobre la mitad de las filas: adelantado y atrasado se verían igual.
 */
function DeriveBar({
  diff, peak, color, mejor,
}: { diff: number; peak: number; color: string; mejor: boolean }) {
  const ancho = `${Math.min(50, (Math.abs(diff) / peak) * 50)}%`
  return (
    <div className="relative h-2 min-w-24 rounded-full bg-surface-2">
      <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-line" />
      <span
        className="absolute inset-y-0 rounded-full"
        style={{
          width: ancho,
          background: color,
          opacity: 0.75,
          ...(mejor ? { right: '50%' } : { left: '50%' }),
        }}
      />
    </div>
  )
}
