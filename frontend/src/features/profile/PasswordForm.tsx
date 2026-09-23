// Cambio de la propia contraseña. Exige la actual: sin eso, cualquiera que
// encuentre una sesión abierta podría secuestrar la cuenta.
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { KeyRound } from 'lucide-react'
import { api } from '../../lib/api'
import { Field, Modal } from '../../components/ui/primitives'

const MIN = 8
const EMPTY = { current: '', next: '', confirm: '' }

export function PasswordForm({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form, setForm] = useState(EMPTY)
  const [done, setDone] = useState(false)

  // Al abrir se limpia el formulario. Ajuste de estado durante el render
  // (patrón oficial de React) en vez de efecto — igual que SwimmerForm.
  const [prevOpen, setPrevOpen] = useState(open)
  if (prevOpen !== open) {
    setPrevOpen(open)
    if (open) { setForm(EMPTY); setDone(false) }
  }

  const mutation = useMutation({
    mutationFn: () => api.auth.changePassword(form.current, form.next),
    onSuccess: () => setDone(true),
  })

  const mismatch = form.confirm.length > 0 && form.next !== form.confirm
  const valid = form.current.length > 0 && form.next.length >= MIN && form.next === form.confirm

  return (
    <Modal open={open} onClose={onClose} title="Cambiar contraseña">
      {done ? (
        <div className="flex flex-col gap-4">
          <p className="text-[12.5px] text-text-dim">
            Contraseña actualizada. La próxima vez que entres, usa la nueva.
          </p>
          <div className="flex justify-end border-t border-line pt-4">
            <button className="btn btn-primary" onClick={onClose}>Listo</button>
          </div>
        </div>
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => { e.preventDefault(); if (valid) mutation.mutate() }}
        >
          <Field label="Contraseña actual">
            <input
              className="field"
              type="password"
              autoComplete="current-password"
              value={form.current}
              onChange={(e) => setForm({ ...form, current: e.target.value })}
            />
          </Field>

          <Field label="Nueva contraseña">
            <input
              className="field"
              type="password"
              autoComplete="new-password"
              value={form.next}
              onChange={(e) => setForm({ ...form, next: e.target.value })}
            />
            <p className="mt-1.5 text-[10.5px] text-text-faint">Mínimo {MIN} caracteres.</p>
          </Field>

          <Field label="Repetir nueva contraseña">
            <input
              className="field"
              type="password"
              autoComplete="new-password"
              value={form.confirm}
              onChange={(e) => setForm({ ...form, confirm: e.target.value })}
            />
            {mismatch && (
              <p className="mt-1.5 text-[10.5px] text-coral">Las dos contraseñas no coinciden.</p>
            )}
          </Field>

          {mutation.isError && (
            <p className="text-[11.5px] text-coral">{(mutation.error as Error).message}</p>
          )}

          <div className="flex justify-end gap-2.5 border-t border-line pt-4">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={!valid || mutation.isPending}>
              <KeyRound size={14} /> {mutation.isPending ? 'Guardando…' : 'Cambiar'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
