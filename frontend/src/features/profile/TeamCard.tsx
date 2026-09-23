// Tarjeta del equipo: identidad del club, su composición y las acciones que
// solo puede ejecutar el dueño (renombrar y ceder la propiedad).
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Crown, Pencil, Shield, Users, X } from 'lucide-react'
import { api } from '../../lib/api'
import type { Member, Team } from '../../lib/types'
import { SECTION_ACCENT } from '../../lib/constants'
import { Card } from '../../components/ui/primitives'
import { TransferOwnerModal } from './TransferOwnerModal'

export function TeamCard({ team, members }: { team: Team; members: Member[] }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(team.name)
  const [transferOpen, setTransferOpen] = useState(false)
  const queryClient = useQueryClient()
  const accent = SECTION_ACCENT['/perfil']

  const renameMutation = useMutation({
    mutationFn: () => api.teams.rename(name.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team'] })
      // El nombre del equipo también viaja en la sesión y en los miembros.
      queryClient.invalidateQueries({ queryKey: ['session'] })
      queryClient.invalidateQueries({ queryKey: ['members'] })
      setEditing(false)
    },
  })

  const start = () => { setName(team.name); setEditing(true) }
  const valid = name.trim().length >= 2

  return (
    <Card className="card-hover">
      <div className="flex items-start gap-3.5">
        <span
          className="flex size-11 shrink-0 items-center justify-center rounded-xl"
          style={{ color: accent, background: `${accent}1a`, border: `1px solid ${accent}33` }}
        >
          <Shield size={19} strokeWidth={2.1} />
        </span>

        <div className="min-w-0 flex-1">
          <p className="card-title">Equipo</p>
          {editing ? (
            <form
              className="mt-1.5 flex items-center gap-1.5"
              onSubmit={(e) => { e.preventDefault(); if (valid) renameMutation.mutate() }}
            >
              <input
                className="field !py-1.5 !text-[14px]"
                value={name}
                autoFocus
                onChange={(e) => setName(e.target.value)}
              />
              <button type="submit" className="btn btn-primary !px-2.5 !py-1.5"
                      disabled={!valid || renameMutation.isPending} aria-label="Guardar nombre">
                <Check size={13.5} />
              </button>
              <button type="button" className="btn btn-ghost !px-2.5 !py-1.5"
                      onClick={() => setEditing(false)} aria-label="Cancelar">
                <X size={13.5} />
              </button>
            </form>
          ) : (
            <div className="mt-1 flex items-center gap-2">
              <p className="display truncate text-[17px] font-bold leading-tight">{team.name}</p>
              {team.is_owner && (
                <button className="btn btn-ghost !p-1.5" onClick={start} aria-label="Renombrar equipo">
                  <Pencil size={12} />
                </button>
              )}
            </div>
          )}
          {renameMutation.isError && (
            <p className="mt-1 text-[11px] text-coral">{(renameMutation.error as Error).message}</p>
          )}
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-line pt-3.5">
        <Stat label="Entrenadores" value={team.coaches} />
        <Stat label="Atletas" value={team.athletes} />
        <Stat label="Nadadores" value={team.swimmers} />
      </dl>

      <div className="mt-3.5 flex items-center justify-between gap-3 border-t border-line pt-3.5">
        <p className="flex min-w-0 items-center gap-1.5 text-[11.5px] text-text-dim">
          <Crown size={12} className="shrink-0 text-amber" />
          <span className="truncate">
            En jefe: <span className="font-semibold text-text">{team.owner_name ?? '—'}</span>
          </span>
        </p>
        {team.is_owner && (
          <button className="btn btn-ghost !py-1.5 !text-[12px]" onClick={() => setTransferOpen(true)}>
            <Users size={12.5} /> Ceder
          </button>
        )}
      </div>

      <TransferOwnerModal
        open={transferOpen}
        onClose={() => setTransferOpen(false)}
        team={team}
        members={members}
      />
    </Card>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-[9.5px] font-bold uppercase tracking-[0.12em] text-text-faint">{label}</dt>
      <dd className="mono mt-0.5 text-[18px] font-semibold leading-none">{value}</dd>
    </div>
  )
}
