// Zonas del simulador: comparación inicio vs. pico del macrociclo.
import { useState } from 'react'
import type { SimWeek } from '../../lib/types'
import { ZONE_META, ZONE_ORDER } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'

export function SimZones({ weeks }: { weeks: SimWeek[] }) {
  const [mode, setMode] = useState<'inicio' | 'pico'>('inicio')
  if (!weeks.length) return null
  const week = mode === 'inicio' ? weeks[0] : weeks[Math.max(weeks.length - 2, 0)]

  return (
    <Card
      animate={false}
      title="Zonas de entrenamiento (pace /100m)"
      className="card-hover"
      action={
        <div className="flex gap-1.5">
          {(['inicio', 'pico'] as const).map((m) => (
            <button
              key={m}
              className={`btn !px-3 !py-1.5 text-[11px] ${mode === m ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setMode(m)}
            >
              {m === 'inicio' ? 'Semana 1' : 'Semana pico'}
            </button>
          ))}
        </div>
      }
    >
      <div className="grid grid-cols-5 gap-3">
        {ZONE_ORDER.map((zone) => {
          const range = week.zones[zone]
          const meta = ZONE_META[zone]
          return (
            <div
              key={zone}
              className="rounded-xl border px-3 py-3 text-center"
              style={{ borderColor: `${meta.color}28`, background: `${meta.color}0d` }}
            >
              <p className="mono text-[11px] font-bold" style={{ color: meta.color }}>{zone}</p>
              <p className="mt-0.5 text-[8.5px] uppercase tracking-wider text-text-faint">{meta.label}</p>
              <p className="mono mt-2 text-[14px] font-bold">
                {range ? toClock(range.mid, 1) : '—'}
              </p>
              {range && (
                <p className="mono text-[9px] text-text-faint">
                  {toClock(range.min, 1)} – {toClock(range.max, 1)}
                </p>
              )}
              <p className="mono mt-1.5 text-[9.5px]" style={{ color: meta.color }}>
                {week.zone_km[zone] != null ? `${week.zone_km[zone]} km/sem` : ''}
              </p>
            </div>
          )
        })}
      </div>
      <p className="mt-3 text-[10px] text-text-faint">
        Semana {week.week_number} ({week.date_label}) · tiempo esperado {toClock(week.expected_time)} ·
        pace {toClock(week.pace_100m)} /100m
      </p>
    </Card>
  )
}
