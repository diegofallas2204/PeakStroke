// Gestión de atletas: grid de tarjetas + alta/edición en modal.
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Users, Pencil, Trash2, Ruler, Weight } from 'lucide-react'
import { api } from '../../lib/api'
import type { Swimmer } from '../../lib/types'
import { SPECIALTY_LABEL, STROKE_LABEL } from '../../lib/constants'
import { usePageEnter } from '../../hooks/usePageEnter'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, Chip, EmptyState, Spinner } from '../../components/ui/primitives'
import { SwimmerForm } from './SwimmerForm'

const SPECIALTY_COLOR: Record<string, string> = {
  velocidad: '#fb7185', medio_fondo: '#3b82f6', fondo: '#22d3ee', aguas_abiertas: '#34d399',
}

function initials(name: string): string {
  return name.split(' ').slice(0, 2).map((p) => p[0]).join('').toUpperCase()
}

export function SwimmersPage() {
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<Swimmer | null>(null)
  const [showForm, setShowForm] = useState(false)
  const queryClient = useQueryClient()

  const { data: swimmers, isLoading } = useQuery({
    queryKey: ['swimmers', search],
    queryFn: () => api.swimmers.list(search || undefined),
  })

  const removeMutation = useMutation({
    mutationFn: (id: number) => api.swimmers.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['swimmers'] }),
  })

  const ref = usePageEnter([isLoading])

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Atletas"
        subtitle="Registro y perfil deportivo de los nadadores del equipo"
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
            <button className="btn btn-primary" onClick={() => { setEditing(null); setShowForm(true) }}>
              <Plus size={14} /> Nuevo atleta
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
          hint={search ? 'Prueba con otro nombre.' : 'Registra a tu primer nadador para ligarlo a un macrociclo.'}
        />
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {swimmers.map((swimmer) => {
            const color = SPECIALTY_COLOR[swimmer.specialty] ?? '#3b82f6'
            return (
              <Card key={swimmer.id} className="card-hover group">
                <div className="flex items-start gap-3.5">
                  <div
                    className="display flex size-11 shrink-0 items-center justify-center rounded-xl text-[13px] font-bold"
                    style={{ color, background: `${color}1a`, border: `1px solid ${color}33` }}
                  >
                    {initials(swimmer.name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[14px] font-semibold">{swimmer.name}</p>
                    <p className="mt-0.5 text-[11px] text-text-dim">
                      {swimmer.age != null ? `${swimmer.age} años` : 'Edad —'}
                      {swimmer.gender ? ` · ${swimmer.gender}` : ''}
                    </p>
                  </div>
                  <div className="flex gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                    <button
                      className="btn btn-ghost !p-1.5"
                      onClick={() => { setEditing(swimmer); setShowForm(true) }}
                      aria-label={`Editar ${swimmer.name}`}
                    >
                      <Pencil size={12.5} />
                    </button>
                    <button
                      className="btn btn-danger !p-1.5"
                      onClick={() => {
                        if (confirm(`¿Eliminar a ${swimmer.name}? Se borrarán sus planes y tests.`))
                          removeMutation.mutate(swimmer.id)
                      }}
                      aria-label={`Eliminar ${swimmer.name}`}
                    >
                      <Trash2 size={12.5} />
                    </button>
                  </div>
                </div>
                <div className="mt-3.5 flex flex-wrap items-center gap-2">
                  <Chip color={color}>{SPECIALTY_LABEL[swimmer.specialty]}</Chip>
                  <Chip color="#8b93b8">{STROKE_LABEL[swimmer.main_stroke]}</Chip>
                </div>
                <div className="mt-3.5 flex gap-4 border-t border-line pt-3 text-[11px] text-text-dim">
                  <span className="flex items-center gap-1.5">
                    <Weight size={11.5} className="text-text-faint" />
                    {swimmer.weight_kg ? `${swimmer.weight_kg} kg` : '—'}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Ruler size={11.5} className="text-text-faint" />
                    {swimmer.height_cm ? `${swimmer.height_cm} cm` : '—'}
                  </span>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      <SwimmerForm
        open={showForm}
        swimmer={editing}
        onClose={() => setShowForm(false)}
      />
    </div>
  )
}
