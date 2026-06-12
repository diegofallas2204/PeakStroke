// Panel de zonas de entrenamiento de la semana seleccionada:
// rango de pace por zona + km sugeridos según la especialidad del atleta.
import type { Week } from '../../lib/types'
import { SPECIALTY_LABEL, ZONE_META, ZONE_ORDER } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'

export function ZonePanel({ week, specialty }: { week: Week | null; specialty: string }) {
  if (!week) return null
  const maxKm = Math.max(...Object.values(week.zone_km), 0.001)

  return (
    <Card title={`Zonas · Semana ${week.week_number} (${week.date_label})`} className="card-hover">
      <div className="flex flex-col">
        {ZONE_ORDER.map((zone) => {
          const range = week.zones[zone]
          const meta = ZONE_META[zone]
          const km = week.zone_km[zone] ?? 0
          return (
            <div key={zone} className="border-b border-line py-2.5 last:border-none">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className="mono rounded-md px-1.5 py-0.5 text-[10px] font-bold"
                    style={{ color: meta.color, background: `${meta.color}1a` }}
                  >
                    {zone}
                  </span>
                  <span className="text-[10.5px] text-text-dim">{meta.label}</span>
                </div>
                <span className="mono text-[12px] font-semibold">
                  {range ? `${toClock(range.min, 1)}–${toClock(range.max, 1)}` : 'No aplica'}
                </span>
              </div>
              {range && (
                <div className="mt-1.5 flex items-center gap-2">
                  <div className="h-1 flex-1 overflow-hidden rounded-full bg-surface-3">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${(km / maxKm) * 100}%`, background: meta.color, opacity: 0.8 }}
                    />
                  </div>
                  <span className="mono w-14 text-right text-[10px] text-text-dim">{km} km</span>
                </div>
              )}
            </div>
          )
        })}
      </div>
      <p className="mt-3 text-[10px] leading-relaxed text-text-faint">
        Pace objetivo por 100m calculado sobre el tiempo esperado de la semana.
        Distribución de km sugerida para especialidad{' '}
        <span className="font-semibold text-text-dim">{SPECIALTY_LABEL[specialty] ?? specialty}</span>.
      </p>
    </Card>
  )
}
