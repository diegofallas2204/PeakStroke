// Selector compartido: macrociclo -> atleta -> prueba objetivo.
//
// **Un desplegable con una sola opción no es un filtro, es ruido.** Cada uno de
// los tres se dibuja como etiqueta cuando no hay nada entre lo que elegir, y eso
// resuelve de paso lo que se pedía por rol: un atleta solo se ve a sí mismo
// —el backend ya acota la lista a su ficha— así que su selector de atleta
// desaparece solo, sin un `if (isAthlete)` que mantener en paralelo al scoping.
//
// El caso del atleta se comprueba igualmente, y no por desconfianza del
// backend: `plan.athletes` podría traer más de una fila el día que un atleta
// pueda ver a un compañero por alguna razón nueva, y elegirlo aquí seguiría sin
// tener sentido para él.
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { api } from '../../lib/api'
import type { AthleteEvent, AthletePlan, Plan } from '../../lib/types'
import { STROKE_LABEL } from '../../lib/constants'
import { useIsAthlete } from '../../hooks/useSession'

export interface EventSelection {
  plan: Plan
  athlete: AthletePlan
  event: AthleteEvent
}

export function EventPicker({
  onChange,
}: { onChange: (selection: EventSelection | null) => void }) {
  const { data: plans } = useQuery({ queryKey: ['plans'], queryFn: api.plans.list })
  const isAthlete = useIsAthlete()
  const [planId, setPlanId] = useState<number | null>(null)
  const [athleteId, setAthleteId] = useState<number | null>(null)
  const [eventId, setEventId] = useState<number | null>(null)

  const plan = useMemo(
    () => plans?.find((p) => p.id === planId) ?? plans?.find((p) => p.status === 'active') ?? plans?.[0] ?? null,
    [plans, planId],
  )
  const athlete = useMemo(
    () => plan?.athletes.find((a) => a.id === athleteId) ?? plan?.athletes[0] ?? null,
    [plan, athleteId],
  )
  const event = useMemo(
    () => athlete?.events.find((e) => e.id === eventId) ?? athlete?.events[0] ?? null,
    [athlete, eventId],
  )

  useEffect(() => {
    onChange(plan && athlete && event ? { plan, athlete, event } : null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan?.id, athlete?.id, event?.id])

  if (!plans?.length) return null

  const atletas = plan?.athletes ?? []
  const pruebas = athlete?.events ?? []
  const eligeAtleta = !isAthlete && atletas.length > 1

  return (
    <div className="flex flex-wrap items-center gap-2.5" data-animate>
      {plans.length > 1 ? (
        <select
          className="field !w-auto min-w-44"
          value={plan?.id ?? ''}
          onChange={(e) => { setPlanId(Number(e.target.value)); setAthleteId(null); setEventId(null) }}
        >
          {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      ) : (
        <Etiqueta label="Macrociclo">{plan?.name}</Etiqueta>
      )}

      {eligeAtleta ? (
        <select
          className="field !w-auto min-w-44"
          value={athlete?.id ?? ''}
          onChange={(e) => { setAthleteId(Number(e.target.value)); setEventId(null) }}
        >
          {atletas.map((a) => <option key={a.id} value={a.id}>{a.swimmer_name}</option>)}
        </select>
      ) : (
        <Etiqueta label={isAthlete ? 'Tú' : 'Atleta'}>
          {athlete?.swimmer_name ?? 'Sin atletas asignados'}
        </Etiqueta>
      )}

      {pruebas.length > 1 ? (
        <select
          className="field !w-auto min-w-40"
          value={event?.id ?? ''}
          onChange={(e) => setEventId(Number(e.target.value))}
        >
          {pruebas.map((ev) => (
            <option key={ev.id} value={ev.id}>
              {ev.distance}m {STROKE_LABEL[ev.stroke] ?? ev.stroke}
            </option>
          ))}
        </select>
      ) : (
        <Etiqueta label="Prueba">
          {event ? `${event.distance}m ${STROKE_LABEL[event.stroke] ?? event.stroke}` : 'Sin pruebas'}
        </Etiqueta>
      )}
    </div>
  )
}

/** El valor único de un filtro que no lo es. Mismo alto que un `.field`. */
function Etiqueta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="flex items-baseline gap-2 rounded-[10px] border border-line bg-surface-2/50 px-3 py-2 text-[13px]">
      <span className="text-[10px] uppercase tracking-wide text-text-faint">{label}</span>
      <span className="font-semibold">{children}</span>
    </span>
  )
}
