// Apuntar (o corregir) una sesión: cuatro números y una nota.
//
// Está pensado para abrirse en dos toques DESPUÉS de nadar (decisión de C7,
// opción A): la fecha llega puesta en hoy y el RPE se elige con un toque, con la
// escala a la vista. Lo derivado —ritmo, carga— no se pregunta: sale solo.
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../lib/api'
import type { TrainingSession, TrainingSessionInput } from '../../lib/types'
import { RPE_LABEL } from '../../lib/constants'
import { isoDay, parseHoursMinutes, toClock, toHoursMinutes } from '../../lib/format'
import { Field, Modal } from '../../components/ui/primitives'

const RPE_VALUES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

/** Del verde al coral: la escala se lee de un vistazo. */
function rpeColor(rpe: number): string {
  if (rpe <= 3) return '#34d399'
  if (rpe <= 5) return '#22d3ee'
  if (rpe <= 7) return '#fbbf24'
  return '#fb7185'
}

export function SessionForm({
  open, swimmerId, session, onClose,
}: {
  open: boolean
  swimmerId: number | null
  /** Con sesión, edita; sin ella, apunta una nueva. */
  session: TrainingSession | null
  onClose: () => void
}) {
  const [date, setDate] = useState('')
  const [meters, setMeters] = useState('')
  const [duration, setDuration] = useState('')
  const [rpe, setRpe] = useState<number | null>(null)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const queryClient = useQueryClient()

  // Al abrir se cargan los campos (de la sesión, o vacíos con la fecha de hoy).
  // Ajuste de estado durante el render, como `TestForm`, en vez de un efecto.
  // Arranca en `false` y no en `open`: con `?nueva=1` el formulario NACE abierto,
  // y sin una transición que detectar los campos se quedaban sin rellenar (la
  // fecha vacía). Lo destapó el QA del 2026-10-01.
  const [prevOpen, setPrevOpen] = useState(false)
  if (open !== prevOpen) {
    setPrevOpen(open)
    if (open) {
      setError('')
      setDate(session?.session_date ?? isoDay(new Date()))
      setMeters(session ? String(session.distance_m) : '')
      setDuration(session ? toHoursMinutes(session.duration_s) : '')
      setRpe(session?.rpe ?? null)
      setNotes(session?.notes ?? '')
    }
  }

  const distance = Number(meters)
  // Al corregir, si la duración no se tocó se reenvía la guardada al segundo:
  // el campo enseña minutos y releerlo redondearía (5430 s → 5400 s), moviendo
  // ritmo y carga sin que nadie lo pidiera.
  const durationS = session && duration === toHoursMinutes(session.duration_s)
    ? session.duration_s
    : parseHoursMinutes(duration)
  const pace = distance > 0 && durationS ? (durationS / distance) * 100 : null

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
    queryClient.invalidateQueries({ queryKey: ['training-load'] })
  }

  const mutation = useMutation({
    mutationFn: (data: TrainingSessionInput) =>
      session ? api.sessions.update(session.id, data) : api.sessions.create(swimmerId!, data),
    onSuccess: () => { invalidate(); onClose() },
    onError: (e: Error) => setError(e.message),
  })

  const submit = () => {
    setError('')
    if (!session && swimmerId == null) { setError('Selecciona un atleta primero.'); return }
    if (!date) { setError('Falta la fecha.'); return }
    if (date > isoDay(new Date())) { setError('La sesión se apunta después de nadarla: la fecha no puede ser futura.'); return }
    if (!Number.isInteger(distance) || distance <= 0) {
      setError('Los metros son un número entero mayor que cero.'); return
    }
    if (durationS == null) {
      setError('La duración va en h:mm (1:30) o en minutos (90).'); return
    }
    mutation.mutate({
      session_date: date, distance_m: distance, duration_s: durationS,
      rpe, notes: notes.trim() || null,
    })
  }

  return (
    <Modal open={open} onClose={onClose} title={session ? 'Corregir sesión' : 'Apuntar sesión'}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field label="Fecha">
          {/* Se apunta DESPUÉS de nadar (C7, opción A): una fecha futura es un error de tecleo. */}
          <input
            type="date" className="field" value={date} max={isoDay(new Date())}
            onChange={(e) => setDate(e.target.value)}
          />
        </Field>
        <Field label="Metros">
          <input
            className="field mono" inputMode="numeric" placeholder="4500"
            value={meters} onChange={(e) => setMeters(e.target.value.replace(/\D/g, ''))}
          />
        </Field>
        <Field label="Duración (h:mm)">
          <input
            className="field mono" placeholder="1:30"
            value={duration} onChange={(e) => setDuration(e.target.value)}
          />
        </Field>
      </div>
      <p className="mt-1.5 text-[10.5px] text-text-faint">
        La duración es la sesión entera, descansos incluidos: de la primera salida a la última llegada.
        {pace != null && <> Ritmo medio: <span className="mono text-text-dim">{toClock(pace, 1)} /100m</span>.</>}
      </p>

      <Field label="Esfuerzo percibido de la sesión (RPE)" className="mt-4">
        <div className="grid grid-cols-5 gap-1.5 sm:grid-cols-10" role="radiogroup" aria-label="RPE">
          {RPE_VALUES.map((v) => {
            const active = rpe === v
            const color = rpeColor(v)
            return (
              <button
                key={v} type="button" role="radio" aria-checked={active}
                title={RPE_LABEL[v]}
                aria-label={RPE_LABEL[v] ? `${v} · ${RPE_LABEL[v]}` : String(v)}
                onClick={() => setRpe(active ? null : v)}
                className="mono rounded-lg border py-2 text-[13px] font-bold transition-colors"
                style={active
                  ? { color, background: `${color}24`, borderColor: `${color}80` }
                  : { borderColor: 'var(--color-line)', color: 'var(--color-text-dim)' }}
              >
                {v}
              </button>
            )
          })}
        </div>
        <p className="mt-1.5 text-[11px] text-text-dim">
          {rpe != null
            ? <>{rpe} · {RPE_LABEL[rpe] ?? 'entre dos marcas de la escala'}</>
            : '¿Cómo de dura fue la sesión entera? 1 muy, muy fácil · 5 difícil · 10 máximo. Opcional.'}
        </p>
      </Field>

      <Field label="Notas" className="mt-4">
        <input
          className="field" value={notes} maxLength={2000}
          onChange={(e) => setNotes(e.target.value)} placeholder="Qué se nadó, sensaciones…"
        />
      </Field>

      {error && <p className="mt-3 text-xs text-coral">{error}</p>}

      <footer className="mt-5 flex justify-end gap-2.5">
        <button className="btn btn-ghost" onClick={onClose}>Cancelar</button>
        <button className="btn btn-primary" onClick={submit} disabled={mutation.isPending}>
          {session ? 'Guardar cambios' : 'Apuntar sesión'}
        </button>
      </footer>
    </Modal>
  )
}
