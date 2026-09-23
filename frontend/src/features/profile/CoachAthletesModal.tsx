// Qué atletas lleva un entrenador. Muchos a muchos: un nadador puede estar a
// cargo de varios entrenadores (principal, de velocidad, físico…).
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Search, Users } from 'lucide-react'
import { api } from '../../lib/api'
import type { Member } from '../../lib/types'
import { SPECIALTY_LABEL } from '../../lib/constants'
import { initials } from '../../lib/format'
import { EmptyState, Modal, Spinner } from '../../components/ui/primitives'

export function CoachAthletesModal({
  open, onClose, coach,
}: { open: boolean; onClose: () => void; coach: Member | null }) {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Set<number> | null>(null)
  const queryClient = useQueryClient()

  const { data: swimmers } = useQuery({
    queryKey: ['swimmers', ''],
    queryFn: () => api.swimmers.list(),
    enabled: open,
  })
  const { data: asignados, isLoading } = useQuery({
    queryKey: ['coach-athletes', coach?.id],
    queryFn: () => api.teams.coachAthletes(coach!.id),
    enabled: open && coach != null,
  })

  // La selección arranca de lo que ya hay guardado, una sola vez por apertura.
  const [prevKey, setPrevKey] = useState<string | null>(null)
  const key = open && asignados ? `${coach?.id}:${asignados.join(',')}` : null
  if (key !== prevKey) {
    setPrevKey(key)
    setSelected(key ? new Set(asignados) : null)
  }

  const mutation = useMutation({
    mutationFn: () => api.teams.setCoachAthletes(coach!.id, [...(selected ?? [])]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['coach-athletes'] })
      onClose()
    },
  })

  // Actualización funcional, no `new Set(selected)`: con la forma capturada,
  // varios clics dentro del mismo render leen el mismo estado viejo y solo
  // sobrevive el último. Con marcado rápido se perdían selecciones.
  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev ?? [])
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const visibles = (swimmers ?? []).filter(
    (s) => !search || s.name.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={coach ? `Atletas de ${coach.name}` : 'Atletas a cargo'}
    >
      {isLoading || selected === null ? (
        <Spinner />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint" />
            <input
              className="field !pl-9"
              placeholder="Buscar atleta…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {!visibles.length ? (
            <EmptyState
              icon={<Users size={24} />}
              title="Sin resultados"
              hint="Ningún atleta del equipo coincide con la búsqueda."
            />
          ) : (
            <div className="flex max-h-[46vh] flex-col gap-1.5 overflow-y-auto pr-0.5">
              {visibles.map((s) => {
                const active = selected.has(s.id)
                return (
                  <button
                    key={s.id}
                    type="button"
                    role="checkbox"
                    aria-checked={active}
                    onClick={() => toggle(s.id)}
                    className="flex items-center gap-3 rounded-xl border px-3 py-2 text-left transition-colors duration-200"
                    style={{
                      borderColor: active ? 'rgba(129,140,248,.45)' : 'var(--color-line)',
                      background: active ? 'rgba(129,140,248,.1)' : 'var(--color-surface-2)',
                    }}
                  >
                    <span
                      className="display flex size-8 shrink-0 items-center justify-center rounded-lg text-[10.5px] font-bold"
                      style={{ color: '#818cf8', background: 'rgba(129,140,248,.14)' }}
                    >
                      {initials(s.name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-semibold">{s.name}</span>
                      <span className="block truncate text-[11px] text-text-dim">
                        {SPECIALTY_LABEL[s.specialty] ?? s.specialty}
                      </span>
                    </span>
                    <span
                      className="flex size-5 shrink-0 items-center justify-center rounded-md border"
                      style={{
                        borderColor: active ? '#818cf8' : 'var(--color-line-strong)',
                        background: active ? '#818cf8' : 'transparent',
                      }}
                    >
                      {active && <Check size={12} className="text-white" />}
                    </span>
                  </button>
                )
              })}
            </div>
          )}

          {mutation.isError && (
            <p className="text-[11.5px] text-coral">{(mutation.error as Error).message}</p>
          )}

          <div className="flex items-center justify-between gap-3 border-t border-line pt-4">
            <p className="text-[11.5px] text-text-dim">
              {selected.size} {selected.size === 1 ? 'atleta' : 'atletas'} a cargo
            </p>
            <div className="flex gap-2.5">
              <button type="button" className="btn btn-ghost" onClick={onClose}>Cancelar</button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={mutation.isPending}
                onClick={() => mutation.mutate()}
              >
                {mutation.isPending ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  )
}
