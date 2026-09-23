// Tiempos de entrenamiento: ritmo objetivo y salida por zona.
//
// Una prescripción son dos números —"10×100 a 1:18 salida 1:30"— y hasta el
// 2026-08-10 la aplicación solo daba el primero. Esta tarjeta da el segundo.
//
// Las zonas NO se calculan aquí ni en su endpoint: salen del ritmo de la semana
// del macrociclo, que es la única fuente de zonas del sistema. Por eso, sin
// macrociclo asignado, la tarjeta dice qué falta en vez de inventarse un ritmo.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Timer } from 'lucide-react'
import { api } from '../../lib/api'
import { ZONE_META } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { Card, Spinner } from '../../components/ui/primitives'

/** Distancias de repetición que un entrenador escribe de verdad en la pizarra. */
const REP_DISTANCES = [50, 100, 200, 400]

export function TrainingIntervalsCard({ testId }: { testId: number }) {
  const [repDistance, setRepDistance] = useState(100)

  const { data, isLoading } = useQuery({
    queryKey: ['training-intervals', testId, repDistance],
    queryFn: () => api.aerobic.trainingIntervals(testId, repDistance),
  })

  return (
    <Card
      className="card-hover"
      title={
        <div className="flex w-full items-center justify-between gap-3">
          <span>Tiempos de entrenamiento</span>
          <div className="flex gap-1">
            {REP_DISTANCES.map((d) => (
              <button
                key={d}
                className={`mono rounded-md px-2 py-1 text-[10px] font-bold transition-colors ${
                  d === repDistance
                    ? 'bg-[rgba(59,130,246,.16)] text-accent-soft'
                    : 'text-text-faint hover:text-text-dim'
                }`}
                onClick={() => setRepDistance(d)}
              >
                ×{d}
              </button>
            ))}
          </div>
        </div>
      }
    >
      {isLoading ? (
        <Spinner />
      ) : !data?.zones.length ? (
        <div className="flex items-center gap-3 py-2 text-xs text-text-dim">
          <Timer size={18} className="shrink-0 text-text-faint" />
          <p className="leading-relaxed">
            Sin macrociclo asignado no hay ritmo de referencia del que colgar las
            zonas. Inscribe al atleta en un macrociclo y los tiempos de
            entrenamiento salen solos.
          </p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Zona</th>
                  <th>Ritmo /100</th>
                  <th>Nado ×{repDistance}</th>
                  <th>Descanso</th>
                  <th>Salida</th>
                </tr>
              </thead>
              <tbody>
                {data.zones.map((z) => {
                  const meta = ZONE_META[z.zone]
                  return (
                    <tr key={z.zone}>
                      <td>
                        <div className="flex items-center gap-2">
                          <span
                            className="mono rounded-md px-1.5 py-0.5 text-[10px] font-bold"
                            style={{ color: meta?.color, background: `${meta?.color}1a` }}
                          >
                            {z.zone}
                          </span>
                          <span className="text-[10.5px] text-text-dim">{z.label}</span>
                        </div>
                      </td>
                      <td className="mono">{toClock(z.pace_100, 1)}</td>
                      <td className="mono">{toClock(z.work, 1)}</td>
                      <td className="mono text-text-dim">{z.rest.toFixed(0)}s</td>
                      <td className="mono font-bold" style={{ color: meta?.color }}>
                        {toClock(z.interval, 0)}
                        {/* Solo cuando aprieta más que lo que el atleta demostró
                            aguantar: el caso al revés no le dice nada a nadie. */}
                        {z.denser_than_measured && (
                          <span
                            className="ml-1.5 text-[9px] font-normal text-amber"
                            title={`Más apretado que la densidad de su test (${toClock(z.measured_interval ?? 0, 0)})`}
                          >
                            ▲
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <p className="mt-3 text-[10px] leading-relaxed text-text-faint">
            Ritmo por zona sobre {toClock(data.reference_pace ?? 0, 1)}/100m
            {data.event_label && <> del {data.event_label}</>}
            {data.reference_week != null && <> en la semana {data.reference_week}</>}.
            La salida se cuadra al reloj de pared (múltiplos de 5 s) y el descanso
            crece con la intensidad de la zona.
            {data.measured_ratio != null && (
              <> El ▲ marca las que aprietan más que la densidad medida en este test.</>
            )}
          </p>
        </>
      )}
    </Card>
  )
}
