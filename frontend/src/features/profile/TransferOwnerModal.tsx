// Cesión de la propiedad del equipo a otro entrenador.
// Es la operación más delicada de la sección: quien la ejecuta deja de poder
// deshacerla, así que exige elegir explícitamente y confirmar.
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Crown, TriangleAlert } from 'lucide-react'
import { api } from '../../lib/api'
import type { Member, Team } from '../../lib/types'
import { initials } from '../../lib/format'
import { EmptyState, Field, Modal } from '../../components/ui/primitives'

export function TransferOwnerModal({
  open, onClose, team, members,
}: { open: boolean; onClose: () => void; team: Team; members: Member[] }) {
  const [selected, setSelected] = useState<number | null>(null)
  const queryClient = useQueryClient()

  const [prevOpen, setPrevOpen] = useState(open)
  if (prevOpen !== open) {
    setPrevOpen(open)
    if (open) setSelected(null)
  }

  // Solo entrenadores activos distintos del dueño actual: el backend rechaza
  // todo lo demás, así que no tiene sentido ofrecerlo.
  const elegibles = members.filter(
    (m) => m.role === 'coach' && m.is_active && m.id !== team.owner_id,
  )

  const mutation = useMutation({
    mutationFn: () => api.teams.transfer(selected as number),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team'] })
      queryClient.invalidateQueries({ queryKey: ['members'] })
      queryClient.invalidateQueries({ queryKey: ['session'] })
      // Los macrociclos visibles cambian: quien cede deja de verlo todo.
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      onClose()
    },
  })

  return (
    <Modal open={open} onClose={onClose} title="Ceder la propiedad del equipo">
      {!elegibles.length ? (
        <EmptyState
          icon={<Crown size={24} />}
          title="No hay a quién cederla"
          hint="Solo puede ser dueño un entrenador activo del equipo. Crea o restaura una cuenta de entrenador primero."
        />
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => { e.preventDefault(); if (selected) mutation.mutate() }}
        >
          <div
            className="flex items-start gap-3 rounded-xl px-3.5 py-3"
            style={{ background: 'rgba(251,191,36,.1)', border: '1px solid rgba(251,191,36,.22)' }}
          >
            <TriangleAlert size={15} className="mt-0.5 shrink-0 text-amber" />
            <p className="text-[11.5px] leading-relaxed text-text-dim">
              Pasarás a ser un entrenador más: dejarás de ver los macrociclos que no lleves y
              solo el nuevo dueño podrá volver a transferir la propiedad.
            </p>
          </div>

          <Field label="Nuevo entrenador en jefe">
            <div className="flex flex-col gap-1.5">
              {elegibles.map((m) => {
                const active = selected === m.id
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setSelected(m.id)}
                    aria-pressed={active}
                    className="flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors duration-200"
                    style={{
                      borderColor: active ? 'rgba(251,191,36,.45)' : 'var(--color-line)',
                      background: active ? 'rgba(251,191,36,.1)' : 'var(--color-surface-2)',
                    }}
                  >
                    <span
                      className="display flex size-8 shrink-0 items-center justify-center rounded-lg text-[10.5px] font-bold"
                      style={{ color: '#818cf8', background: 'rgba(129,140,248,.14)' }}
                    >
                      {initials(m.name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-semibold">{m.name}</span>
                      <span className="block truncate text-[11px] text-text-dim">{m.email}</span>
                    </span>
                    {active && <Crown size={14} className="shrink-0 text-amber" />}
                  </button>
                )
              })}
            </div>
          </Field>

          {mutation.isError && (
            <p className="text-[11.5px] text-coral">{(mutation.error as Error).message}</p>
          )}

          <div className="flex justify-end gap-2.5 border-t border-line pt-4">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={!selected || mutation.isPending}>
              <Crown size={14} /> {mutation.isPending ? 'Cediendo…' : 'Ceder la propiedad'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}
