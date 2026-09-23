// Asignar atleta a un macrociclo: pruebas objetivo + verificación de
// factibilidad en vivo contra el motor de predicción.
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, UserPlus, ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react'
import { api } from '../../lib/api'
import type { Feasibility, Plan } from '../../lib/types'
import { DISTANCES, coerceStroke, strokeOptionsForDistance } from '../../lib/constants'
import { tryToSeconds } from '../../lib/format'
import { Field, Modal } from '../../components/ui/primitives'

interface EventDraft { distance: number; stroke: string; current: string; goal: string }

const FEAS_META = {
  ok: { icon: ShieldCheck, color: '#34d399', bg: 'rgba(52,211,153,.09)' },
  warning: { icon: ShieldAlert, color: '#fbbf24', bg: 'rgba(251,191,36,.09)' },
  aggressive: { icon: ShieldX, color: '#fb7185', bg: 'rgba(251,113,133,.09)' },
} as const

function FeasibilityBanner({ feasibility }: { feasibility: Feasibility }) {
  const meta = FEAS_META[feasibility.status]
  const Icon = meta.icon
  return (
    <div
      className="flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-[11.5px] leading-relaxed"
      style={{ color: meta.color, background: meta.bg, borderColor: `${meta.color}33` }}
    >
      <Icon size={15} className="mt-0.5 shrink-0" />
      <span>
        {feasibility.message}
        {feasibility.recommended_weeks && (
          <> Sugerencia: <strong>{feasibility.recommended_weeks} semanas</strong>.</>
        )}
      </span>
    </div>
  )
}

export function AssignAthleteModal({ plan, onClose }: { plan: Plan | null; onClose: () => void }) {
  const [swimmerId, setSwimmerId] = useState<number | ''>('')
  const [aerobicBase, setAerobicBase] = useState('')
  const [events, setEvents] = useState<EventDraft[]>([{ distance: 100, stroke: 'libre', current: '', goal: '' }])
  const [feasibilities, setFeasibilities] = useState<(Feasibility | null)[]>([null])
  const [error, setError] = useState('')
  const queryClient = useQueryClient()

  // La lista la decide el backend, no un filtro local: además de los que ya
  // están en este macrociclo, quedan fuera los comprometidos con otro que sigue
  // vivo. Un atleta, un macrociclo (`plans/enrollment.py`); el POST rechaza lo
  // mismo, así que esto no es una restricción de la interfaz.
  const { data: available = [] } = useQuery({
    queryKey: ['assignable-athletes', plan?.id],
    queryFn: () => api.plans.assignableAthletes(plan!.id),
    enabled: plan != null,
  })
  const { data: tests } = useQuery({
    queryKey: ['aerobic', swimmerId],
    queryFn: () => api.aerobic.list(swimmerId as number),
    enabled: swimmerId !== '',
  })

  // Ajustes de estado durante el render (patrón oficial de React) en vez de efectos:
  // al abrir con un macrociclo se limpia el formulario; al llegar los tests del
  // atleta se autocompleta la base aeróbica desde el último.
  const [prevPlan, setPrevPlan] = useState(plan)
  if (plan !== prevPlan) {
    setPrevPlan(plan)
    if (plan) {
      setSwimmerId(''); setAerobicBase('')
      setEvents([{ distance: 100, stroke: 'libre', current: '', goal: '' }])
      setFeasibilities([null]); setError('')
    }
  }
  const [prevTests, setPrevTests] = useState(tests)
  if (tests !== prevTests) {
    setPrevTests(tests)
    if (tests?.length) setAerobicBase(String(tests[0].avg_per100))
  }

  // Factibilidad en vivo (debounce) por cada prueba completa.
  useEffect(() => {
    if (!plan) return
    const timer = setTimeout(async () => {
      const results = await Promise.all(events.map(async (ev) => {
        const current = tryToSeconds(ev.current)
        const goal = tryToSeconds(ev.goal)
        if (current == null || goal == null) return null
        try {
          const selectedSwimmer = available.find((s) => s.id === swimmerId)
          const sim = await api.simulator.run({
            distance: ev.distance, stroke: ev.stroke, current_time: current,
            goal_time: goal, total_weeks: plan.total_weeks,
            weeks_per_micro: plan.weeks_per_micro, total_km: plan.total_km,
            curve: plan.progression_curve,
            n_mac: plan.n_mac,
            swimmer_age: selectedSwimmer?.age ?? undefined,
          })
          return sim.feasibility
        } catch { return null }
      }))
      setFeasibilities(results)
    }, 350)
    return () => clearTimeout(timer)
  }, [events, plan, available, swimmerId])

  const mutation = useMutation({
    mutationFn: () => api.plans.addAthlete(plan!.id, {
      swimmer_id: swimmerId,
      aerobic_base: aerobicBase ? Number(aerobicBase) : null,
      aerobic_base_source: tests?.length && aerobicBase === String(tests[0].avg_per100)
        ? tests[0].test_type.toLowerCase().slice(0, 12) : 'manual',
      events: events.map((ev, i) => ({
        priority: i + 1, distance: ev.distance, stroke: ev.stroke,
        current_time: tryToSeconds(ev.current), goal_time: tryToSeconds(ev.goal),
      })),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['team-week'] })
      onClose()
    },
    onError: (e: Error) => setError(e.message),
  })

  const submit = () => {
    setError('')
    if (swimmerId === '') { setError('Selecciona un atleta.'); return }
    for (const ev of events) {
      const current = tryToSeconds(ev.current)
      const goal = tryToSeconds(ev.goal)
      if (current == null || goal == null) { setError('Completa los tiempos de todas las pruebas (formato m:ss.cc o ss.cc).'); return }
      if (goal >= current) { setError('El tiempo meta debe ser menor al actual.'); return }
    }
    mutation.mutate()
  }

  return (
    <Modal open={plan !== null} onClose={onClose} title={`Agregar atleta · ${plan?.name ?? ''}`} wide>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Atleta">
          <select className="field" value={swimmerId} disabled={!available.length}
            onChange={(e) => setSwimmerId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">Seleccionar…</option>
            {available.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          {!available.length && (
            <p className="mt-1.5 text-[10.5px] text-text-faint">
              Nadie libre: el resto del equipo ya está en este u otro macrociclo en curso.
            </p>
          )}
        </Field>
        <Field label="Base aeróbica (s/100m)">
          <input
            className="field mono" value={aerobicBase}
            onChange={(e) => setAerobicBase(e.target.value)}
            placeholder="Del último T-30/T-15 o manual"
          />
          {tests?.length ? (
            <p className="mt-1 text-[10px] text-mint">
              Autocompletada del último test ({tests[0].test_type} · {tests[0].test_date})
            </p>
          ) : swimmerId !== '' ? (
            <p className="mt-1 text-[10px] text-text-faint">Sin tests registrados: puedes ingresarla manualmente.</p>
          ) : null}
        </Field>
      </div>

      <div className="mt-5">
        <div className="mb-2.5 flex items-center justify-between">
          <span className="card-title">Pruebas objetivo (máx. 3 recomendadas)</span>
          <button
            className="btn btn-ghost !px-2.5 !py-1.5 text-[11px]"
            onClick={() => { setEvents((e) => [...e, { distance: 100, stroke: 'libre', current: '', goal: '' }]); setFeasibilities((f) => [...f, null]) }}
          >
            <Plus size={12} /> Prueba
          </button>
        </div>
        <div className="flex flex-col gap-3">
          {events.map((ev, i) => (
            <div key={i} className="rounded-xl border border-line bg-surface-2 p-3">
              <div className="grid grid-cols-[90px_120px_1fr_1fr_34px] items-end gap-2.5">
                <Field label="Distancia">
                  <select className="field !py-1.5" value={ev.distance}
                    onChange={(e) => setEvents((evs) => evs.map((x, j) => {
                      if (j !== i) return x
                      const distance = Number(e.target.value)
                      // Autocorrige el estilo si la nueva distancia lo invalida (p. ej. 400 mariposa → libre).
                      return { ...x, distance, stroke: coerceStroke(distance, x.stroke) }
                    }))}>
                    {DISTANCES.map((d) => <option key={d} value={d}>{d}m</option>)}
                  </select>
                </Field>
                <Field label="Estilo">
                  <select className="field !py-1.5" value={ev.stroke}
                    onChange={(e) => setEvents((evs) => evs.map((x, j) => j === i ? { ...x, stroke: e.target.value } : x))}>
                    {strokeOptionsForDistance(ev.distance).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </Field>
                <Field label="Tiempo actual">
                  <input className="field mono !py-1.5" placeholder="1:07.80" value={ev.current}
                    onChange={(e) => setEvents((evs) => evs.map((x, j) => j === i ? { ...x, current: e.target.value } : x))} />
                </Field>
                <Field label="Tiempo meta">
                  <input className="field mono !py-1.5" placeholder="1:04.50" value={ev.goal}
                    onChange={(e) => setEvents((evs) => evs.map((x, j) => j === i ? { ...x, goal: e.target.value } : x))} />
                </Field>
                <button
                  className="btn btn-danger mb-0.5 !p-1.5" disabled={events.length === 1}
                  onClick={() => { setEvents((evs) => evs.filter((_, j) => j !== i)); setFeasibilities((f) => f.filter((_, j) => j !== i)) }}
                  aria-label="Quitar prueba"
                >
                  <Trash2 size={12} />
                </button>
              </div>
              {feasibilities[i] && <div className="mt-2.5"><FeasibilityBanner feasibility={feasibilities[i]!} /></div>}
            </div>
          ))}
        </div>
      </div>

      {error && <p className="mt-4 text-xs text-coral">{error}</p>}

      <footer className="mt-6 flex justify-end gap-2.5">
        <button className="btn btn-ghost" onClick={onClose}>Cancelar</button>
        <button className="btn btn-primary" onClick={submit} disabled={mutation.isPending}>
          <UserPlus size={13} /> Asignar y generar plan
        </button>
      </footer>
    </Modal>
  )
}
