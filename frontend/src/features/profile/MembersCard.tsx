// Miembros del equipo, separados por rol. Solo lo ve el entrenador.
//
// Entrenadores y atletas van en bloques distintos en vez de una sola tabla
// ordenada por nombre: en un club se busca "los entrenadores" o "los atletas",
// casi nunca a alguien sin saber de qué grupo es.
import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ClipboardList, Plus, Search, ShieldCheck, ShieldOff, UsersRound } from 'lucide-react'
import { api } from '../../lib/api'
import type { Member } from '../../lib/types'
import { ROLE_META, roleMeta } from '../../lib/constants'
import { initials, toShortDate } from '../../lib/format'
import { Card, Chip, EmptyState, Segmented } from '../../components/ui/primitives'
import { CoachAthletesModal } from './CoachAthletesModal'

type RoleFilter = 'all' | 'coach' | 'athlete'

export function MembersCard({
  members, currentId, onInvite,
}: { members: Member[]; currentId: number; onInvite: () => void }) {
  const [search, setSearch] = useState('')
  const [role, setRole] = useState<RoleFilter>('all')
  const [showRevoked, setShowRevoked] = useState(false)
  const [athletesOf, setAthletesOf] = useState<Member | null>(null)
  const queryClient = useQueryClient()

  const accessMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      api.auth.updateMember(id, { is_active: active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['members'] }),
  })

  const { coaches, athletes, revocados } = useMemo(() => {
    const q = search.trim().toLowerCase()
    const coincide = (m: Member) =>
      !q || m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q) ||
      (m.swimmer_name?.toLowerCase().includes(q) ?? false)
    const visibles = members.filter((m) => coincide(m) && (showRevoked || m.is_active))
    return {
      coaches: visibles.filter((m) => m.role === 'coach'),
      athletes: visibles.filter((m) => m.role === 'athlete'),
      revocados: members.filter((m) => !m.is_active).length,
    }
  }, [members, search, showRevoked])

  const grupos = [
    { key: 'coach' as const, titulo: 'Entrenadores', icono: ClipboardList, filas: coaches },
    { key: 'athlete' as const, titulo: 'Atletas', icono: UsersRound, filas: athletes },
  ].filter((g) => role === 'all' || role === g.key)

  const totalVisible = grupos.reduce((n, g) => n + g.filas.length, 0)

  return (
    <Card
      flush
      title="Miembros del equipo"
      action={
        <button className="btn btn-primary !py-1.5 !text-[12.5px]" onClick={onInvite}>
          <Plus size={13.5} /> Dar acceso
        </button>
      }
    >
      <div className="flex flex-wrap items-center gap-2.5 px-5 pb-4">
        <div className="relative min-w-[180px] flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint" />
          <input
            className="field !py-1.5 !pl-9 !text-[13px]"
            placeholder="Buscar por nombre, email o ficha…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Segmented
          label="Filtrar por rol"
          value={role}
          onChange={setRole}
          accent="#818cf8"
          options={[
            { value: 'all', label: 'Todos' },
            { value: 'coach', label: 'Entrenadores' },
            { value: 'athlete', label: 'Atletas' },
          ]}
        />
        {revocados > 0 && (
          <button
            type="button"
            role="switch"
            aria-checked={showRevoked}
            onClick={() => setShowRevoked(!showRevoked)}
            className="btn btn-ghost !py-1.5 !text-[12px]"
            style={showRevoked ? { borderColor: 'rgba(251,113,133,.35)', color: 'var(--color-coral)' } : undefined}
          >
            {showRevoked ? 'Ocultar' : 'Ver'} revocados ({revocados})
          </button>
        )}
      </div>

      {!totalVisible ? (
        <EmptyState
          icon={<UsersRound size={24} />}
          title={search ? 'Sin resultados' : 'Nadie más tiene acceso'}
          hint={
            search
              ? 'Prueba con otro nombre o quita los filtros.'
              : 'Da acceso a un nadador para que pueda ver su plan y registrar sus tiempos.'
          }
        />
      ) : (
        grupos.map(({ key, titulo, icono: Icono, filas }) => (
          <section key={key} className="mb-1 last:mb-0">
            <header className="flex items-center gap-2 border-y border-line bg-surface-2/40 px-5 py-2">
              <Icono size={12.5} className="shrink-0" style={{ color: ROLE_META[key].color }} />
              <h4 className="card-title !text-[10px]">{titulo}</h4>
              <span className="mono text-[10.5px] text-text-faint">{filas.length}</span>
            </header>

            {!filas.length ? (
              <p className="px-5 py-4 text-[11.5px] text-text-faint">
                Ningún {key === 'coach' ? 'entrenador' : 'atleta'} coincide con el filtro.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Miembro</th>
                      <th>{key === 'coach' ? 'Rol' : 'Ficha deportiva'}</th>
                      <th>Último acceso</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {filas.map((m) => (
                      <MemberRow
                        key={m.id}
                        member={m}
                        isSelf={m.id === currentId}
                        onManageAthletes={() => setAthletesOf(m)}
                        onToggleAccess={(active) => accessMutation.mutate({ id: m.id, active })}
                        busy={accessMutation.isPending}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ))
      )}

      {accessMutation.isError && (
        <p className="px-5 py-3 text-[11.5px] text-coral">
          {(accessMutation.error as Error).message}
        </p>
      )}

      <CoachAthletesModal
        open={athletesOf != null}
        onClose={() => setAthletesOf(null)}
        coach={athletesOf}
      />
    </Card>
  )
}

function MemberRow({
  member: m, isSelf, onManageAthletes, onToggleAccess, busy,
}: {
  member: Member
  isSelf: boolean
  onManageAthletes: () => void
  onToggleAccess: (active: boolean) => void
  busy: boolean
}) {
  const meta = roleMeta(m.role, m.is_owner)
  const esEntrenador = m.role === 'coach'

  return (
    <tr className={m.is_active ? '' : 'opacity-55'}>
      <td>
        <div className="flex items-center gap-2.5">
          <span
            className="display flex size-8 shrink-0 items-center justify-center rounded-lg text-[10.5px] font-bold"
            style={{
              color: meta.color, background: `${meta.color}1a`,
              border: `1px solid ${meta.color}30`,
            }}
          >
            {initials(m.name)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[13px] font-semibold leading-tight">
              {m.name}
              {isSelf && <span className="ml-1.5 text-[10.5px] text-text-faint">(tú)</span>}
            </p>
            <p className="truncate text-[11px] leading-tight text-text-dim">{m.email}</p>
          </div>
        </div>
      </td>
      <td>
        {esEntrenador ? (
          <Chip color={meta.color}>{meta.label}</Chip>
        ) : (
          <span className={m.swimmer_name ? '' : 'text-text-faint'}>
            {m.swimmer_name ?? 'Sin ligar'}
          </span>
        )}
      </td>
      <td className="mono text-[12.5px] text-text-dim">
        {m.last_login_at ? toShortDate(m.last_login_at) : 'Nunca'}
      </td>
      <td className="text-right">
        {!m.is_active && <Chip color="#fb7185">Revocado</Chip>}
        {esEntrenador && m.is_active && (
          <button className="btn btn-ghost ml-2 !py-1.5 !text-[12px]" onClick={onManageAthletes}>
            <UsersRound size={12.5} /> Atletas
          </button>
        )}
        {/* Ni uno mismo ni el dueño pueden quedarse sin acceso: el equipo se
            quedaría sin quien lo administre. Para relevar al dueño hay que
            transferir la propiedad primero, y el backend rechaza ambos casos. */}
        {!isSelf && !m.is_owner && (
          <button
            className={`btn ${m.is_active ? 'btn-danger' : 'btn-ghost'} ml-2 !py-1.5 !text-[12px]`}
            disabled={busy}
            onClick={() => {
              if (m.is_active && !confirm(`¿Revocar el acceso de ${m.name}? Sus datos no se borran.`))
                return
              onToggleAccess(!m.is_active)
            }}
          >
            {m.is_active ? <ShieldOff size={12.5} /> : <ShieldCheck size={12.5} />}
            {m.is_active ? 'Revocar' : 'Restaurar'}
          </button>
        )}
      </td>
    </tr>
  )
}
