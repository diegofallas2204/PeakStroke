// Vista Zonas: la prescripción de la semana, a pantalla completa.
//
// Antes era un cajón de 290px al lado de la tabla, y ahí no cabía lo que una
// zona es: dos números (ritmo y salida) más el volumen sugerido. Con el ancho
// entero cada zona es una ficha legible y la semana se elige desde aquí, sin
// volver a la tabla.
import type { Week } from '../../lib/types'
import { SECTION_ACCENT, SPECIALTY_LABEL, ZONE_META, ZONE_ORDER } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'

const ACENTO = SECTION_ACCENT['/plan-semanal']

export function VistaZonas({
  weeks, week, specialty, currentWeek, onSelectWeek,
}: {
  weeks: Week[]
  week: Week | null
  specialty: string
  currentWeek: number | null
  onSelectWeek: (weekNumber: number) => void
}) {
  if (!week) return null
  // Suelo de 0.001 para no dividir entre cero en una semana sin kilómetros.
  const totalKm = Math.max(Object.values(week.zone_km).reduce((s, v) => s + v, 0), 0.001)

  return (
    <>
      <Card
        title={`Semana ${week.week_number} · ${week.date_label} · ${week.phase}`}
        action={
          <span className="mono text-[11px] text-text-dim">
            {week.planned_km} km · esperado {toClock(week.expected_time)} · pace {toClock(week.pace_100m)}
          </span>
        }
        className="card-hover"
      >
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {weeks.map((w) => {
            const activa = w.week_number === week.week_number
            return (
              <button
                key={w.id}
                type="button"
                onClick={() => onSelectWeek(w.week_number)}
                aria-pressed={activa}
                title={`${w.date_label} · ${w.phase}${w.disabled ? ' · parón' : ''}`}
                className="mono flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold transition-colors"
                style={{
                  opacity: w.disabled ? 0.4 : 1,
                  ...(activa
                    ? { color: ACENTO, background: `${ACENTO}1f`, borderColor: `${ACENTO}55` }
                    : { borderColor: 'var(--color-line)', color: 'var(--color-text-dim)' }),
                }}
              >
                S{w.week_number}
                {w.week_number === currentWeek && (
                  <span className="pulse-dot size-1.5 rounded-full bg-cyan" />
                )}
              </button>
            )
          })}
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {ZONE_ORDER.map((zone) => (
          <ZonaCard key={zone} zone={zone} week={week} totalKm={totalKm} />
        ))}
      </div>

      <p className="text-[10.5px] leading-relaxed text-text-faint" data-animate>
        Pace objetivo por 100m calculado sobre el tiempo esperado de la semana.
        La salida es el intervalo para repeticiones de esa distancia, cuadrado al
        reloj de pared. Distribución de km sugerida para especialidad{' '}
        <span className="font-semibold text-text-dim">{SPECIALTY_LABEL[specialty] ?? specialty}</span>.
      </p>
    </>
  )
}

function ZonaCard({
  zone, week, totalKm,
}: { zone: string; week: Week; totalKm: number }) {
  const meta = ZONE_META[zone]
  const range = week.zones[zone]
  const km = week.zone_km[zone] ?? 0

  return (
    <Card className="card-hover">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className="mono rounded-md px-1.5 py-0.5 text-[11px] font-bold"
            style={{ color: meta.color, background: `${meta.color}1a` }}
          >
            {zone}
          </span>
          <span className="text-[12px] text-text-dim">{meta.label}</span>
        </div>
        <span className="mono text-[11px] text-text-faint">{km} km</span>
      </header>

      {!range ? (
        <p className="mt-4 text-[12px] text-text-faint">No aplica en esta prueba.</p>
      ) : (
        <>
          <p className="display mono mt-3 text-[20px] font-bold leading-none" style={{ color: meta.color }}>
            {toClock(range.min, 1)}–{toClock(range.max, 1)}
          </p>
          <p className="mt-1.5 text-[10.5px] text-text-faint">
            objetivo <span className="mono text-text-dim">{toClock(range.mid, 1)}</span> por 100m
          </p>

          {/* La otra mitad de la prescripción: cada cuánto se sale. */}
          <div className="mt-3 grid grid-cols-3 gap-2 border-t border-line pt-3">
            <Dato label="Salida" valor={toClock(range.send_off, 0)} />
            <Dato label="Repetición" valor={`${range.rep_distance} m`} />
            {/* Un descanso de más de un minuto en segundos hay que traducirlo
                mentalmente; el reloj de pared no. */}
            <Dato label="Descanso" valor={range.rest >= 60 ? toClock(range.rest, 0) : `${Math.round(range.rest)} s`} />
          </div>

          <div className="mt-3 flex items-center gap-2">
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-surface-3">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{ width: `${(km / totalKm) * 100}%`, background: meta.color, opacity: 0.8 }}
              />
            </div>
            <span className="mono w-10 text-right text-[10px] text-text-faint">
              {Math.round((km / totalKm) * 100)}%
            </span>
          </div>
        </>
      )}
    </Card>
  )
}

function Dato({ label, valor }: { label: string; valor: string }) {
  return (
    <div>
      <p className="text-[9px] uppercase tracking-wide text-text-faint">{label}</p>
      <p className="mono mt-0.5 text-[12.5px] font-semibold">{valor}</p>
    </div>
  )
}
