// Selector compartido: macrociclo -> atleta -> prueba objetivo.
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import type { AthleteEvent, AthletePlan, Plan } from '../../lib/types'
import { STROKE_LABEL } from '../../lib/constants'

export interface EventSelection {
  plan: Plan
  athlete: AthletePlan
  event: AthleteEvent
}

export function EventPicker({
  onChange,
}: { onChange: (selection: EventSelection | null) => void }) {
  const { data: plans } = useQuery({ queryKey: ['plans'], queryFn: api.plans.list })
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

  return (
    <div className="flex flex-wrap items-center gap-2.5" data-animate>
      <select
        className="field !w-auto min-w-44"
        value={plan?.id ?? ''}
        onChange={(e) => { setPlanId(Number(e.target.value)); setAthleteId(null); setEventId(null) }}
      >
        {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <select
        className="field !w-auto min-w-44"
        value={athlete?.id ?? ''}
        onChange={(e) => { setAthleteId(Number(e.target.value)); setEventId(null) }}
        disabled={!plan?.athletes.length}
      >
        {!plan?.athletes.length && <option>Sin atletas asignados</option>}
        {plan?.athletes.map((a) => <option key={a.id} value={a.id}>{a.swimmer_name}</option>)}
      </select>
      <select
        className="field !w-auto min-w-40"
        value={event?.id ?? ''}
        onChange={(e) => setEventId(Number(e.target.value))}
        disabled={!athlete?.events.length}
      >
        {athlete?.events.map((ev) => (
          <option key={ev.id} value={ev.id}>
            {ev.distance}m {STROKE_LABEL[ev.stroke] ?? ev.stroke}
          </option>
        ))}
      </select>
    </div>
  )
}
