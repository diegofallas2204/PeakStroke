// Gestión de atletas: el pool completo del equipo, con su estado de acceso.
//
// «Atleta» y «nadador» eran dos cosas en la interfaz —una ficha deportiva y una
// cuenta— y en realidad son una persona. Esta página es la lista única: cada
// tarjeta dice si esa persona ya puede entrar, si tiene un código pendiente o si
// todavía no tiene cuenta. El vínculo se crea canjeando el código, nunca desde
// aquí a solas (ver `LinkCodeModal`).
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, UserPlus, Users } from 'lucide-react'
import { api } from '../../lib/api'
import type { Swimmer } from '../../lib/types'
import { usePageEnter } from '../../hooks/usePageEnter'
import { PageHeader } from '../../components/layout/PageHeader'
import { EmptyState, Spinner } from '../../components/ui/primitives'
import { SwimmerForm } from './SwimmerForm'
import { SwimmerCard } from './SwimmerCard'
import { InviteAthleteModal } from './InviteAthleteModal'
import { LinkCodeModal } from './LinkCodeModal'

export function SwimmersPage() {
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<Swimmer | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [showInvite, setShowInvite] = useState(false)
  const [accessOf, setAccessOf] = useState<Swimmer | null>(null)
  const queryClient = useQueryClient()

  const { data: swimmers, isLoading } = useQuery({
    queryKey: ['swimmers', search],
    queryFn: () => api.swimmers.list(search || undefined),
  })
  // Los códigos llegan aparte y se cruzan por `swimmer_id`: la definición de
  // "código vivo" vive en su módulo y no duplicada en el de atletas.
  const { data: codes } = useQuery({ queryKey: ['link-codes'], queryFn: api.linkCodes.list })
  const codeOf = new Map((codes ?? []).map((c) => [c.swimmer_id, c]))

  // Dar de baja, no borrar: el histórico de entrenamiento del atleta —semanas,
  // tiempos reales, tests— se conserva y puede reactivarse.
  const deactivateMutation = useMutation({
    mutationFn: (id: number) => api.swimmers.deactivate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['swimmers'] }),
  })

  const ref = usePageEnter([isLoading])

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Atletas"
        subtitle="El equipo completo: una persona por tarjeta, con su ficha y su acceso"
        actions={
          <>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint" />
              <input
                className="field !w-52 !pl-9"
                placeholder="Buscar atleta…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            {/* La vía normal de alta: por correo, en un gesto, con su código.
                Crear una ficha suelta —el atleta que no va a entrar a la app—
                sigue estando, pero como acción secundaria: es el caso raro. */}
            <button className="btn btn-ghost" onClick={() => { setEditing(null); setShowForm(true) }}>
              Solo ficha
            </button>
            <button className="btn btn-primary" onClick={() => setShowInvite(true)}>
              <UserPlus size={14} /> Agregar atleta
            </button>
          </>
        }
      />

      {isLoading ? (
        <Spinner />
      ) : !swimmers?.length ? (
        <EmptyState
          icon={<Users size={24} />}
          title={search ? 'Sin resultados' : 'Aún no hay atletas'}
          hint={search
            ? 'Prueba con otro nombre.'
            : 'Agrega a tu primer atleta con el correo con el que se registra al sistema.'}
          action={!search && (
            <button className="btn btn-primary" onClick={() => setShowInvite(true)}>
              <UserPlus size={14} /> Agregar atleta
            </button>
          )}
        />
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {swimmers.map((swimmer) => (
            <SwimmerCard
              key={swimmer.id}
              swimmer={swimmer}
              code={codeOf.get(swimmer.id)}
              onEdit={() => { setEditing(swimmer); setShowForm(true) }}
              onManageAccess={() => setAccessOf(swimmer)}
              onDeactivate={() => {
                if (confirm(
                  `¿Dar de baja a ${swimmer.name}? Sus planes, tiempos y tests se conservan.`,
                ))
                  deactivateMutation.mutate(swimmer.id)
              }}
            />
          ))}
        </div>
      )}

      <InviteAthleteModal open={showInvite} onClose={() => setShowInvite(false)} />
      <SwimmerForm
        open={showForm}
        swimmer={editing}
        onClose={() => setShowForm(false)}
      />
      <LinkCodeModal
        swimmer={accessOf}
        code={accessOf ? codeOf.get(accessOf.id) ?? null : null}
        onClose={() => setAccessOf(null)}
      />
    </div>
  )
}
