// Formulario de alta/edición de atleta.
import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../lib/api'
import type { Swimmer } from '../../lib/types'
import { SPECIALTIES, STROKES } from '../../lib/constants'
import { Field, Modal } from '../../components/ui/primitives'

const EMPTY = {
  name: '', birth_date: '', gender: 'F', specialty: 'medio_fondo',
  main_stroke: 'libre', weight_kg: '', height_cm: '', notes: '',
}

export function SwimmerForm({
  open, swimmer, onClose,
}: { open: boolean; swimmer: Swimmer | null; onClose: () => void }) {
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!open) return
    setError('')
    setForm(swimmer ? {
      name: swimmer.name,
      birth_date: swimmer.birth_date ?? '',
      gender: swimmer.gender ?? 'F',
      specialty: swimmer.specialty,
      main_stroke: swimmer.main_stroke,
      weight_kg: swimmer.weight_kg?.toString() ?? '',
      height_cm: swimmer.height_cm?.toString() ?? '',
      notes: swimmer.notes ?? '',
    } : EMPTY)
  }, [open, swimmer])

  const mutation = useMutation({
    mutationFn: (payload: Partial<Swimmer>) =>
      swimmer ? api.swimmers.update(swimmer.id, payload) : api.swimmers.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['swimmers'] })
      onClose()
    },
    onError: (e: Error) => setError(e.message),
  })

  const set = (key: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = () => {
    if (form.name.trim().length < 2) { setError('El nombre es obligatorio.'); return }
    mutation.mutate({
      name: form.name.trim(),
      birth_date: form.birth_date || null,
      gender: form.gender || null,
      specialty: form.specialty,
      main_stroke: form.main_stroke,
      weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
      height_cm: form.height_cm ? Number(form.height_cm) : null,
      notes: form.notes || null,
    })
  }

  return (
    <Modal open={open} onClose={onClose} title={swimmer ? `Editar · ${swimmer.name}` : 'Nuevo atleta'}>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Nombre completo" className="col-span-2">
          <input className="field" value={form.name} onChange={set('name')} placeholder="Nombre y apellidos" autoFocus />
        </Field>
        <Field label="Fecha de nacimiento">
          <input type="date" className="field" value={form.birth_date} onChange={set('birth_date')} />
        </Field>
        <Field label="Sexo">
          <select className="field" value={form.gender} onChange={set('gender')}>
            <option value="F">Femenino</option>
            <option value="M">Masculino</option>
          </select>
        </Field>
        <Field label="Especialidad">
          <select className="field" value={form.specialty} onChange={set('specialty')}>
            {SPECIALTIES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>
        <Field label="Estilo principal">
          <select className="field" value={form.main_stroke} onChange={set('main_stroke')}>
            {STROKES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>
        <Field label="Peso (kg)">
          <input type="number" className="field" value={form.weight_kg} onChange={set('weight_kg')} min={20} max={150} />
        </Field>
        <Field label="Estatura (cm)">
          <input type="number" className="field" value={form.height_cm} onChange={set('height_cm')} min={100} max={230} />
        </Field>
        <Field label="Notas" className="col-span-2">
          <textarea className="field min-h-16 resize-y" value={form.notes} onChange={set('notes')} placeholder="Historial deportivo, lesiones, observaciones…" />
        </Field>
      </div>
      {error && <p className="mt-3 text-xs text-coral">{error}</p>}
      <footer className="mt-5 flex justify-end gap-2.5">
        <button className="btn btn-ghost" onClick={onClose}>Cancelar</button>
        <button className="btn btn-primary" onClick={submit} disabled={mutation.isPending}>
          {swimmer ? 'Guardar cambios' : 'Crear atleta'}
        </button>
      </footer>
    </Modal>
  )
}
