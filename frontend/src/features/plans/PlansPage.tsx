// Macrociclos: tarjetas de planes existentes + asistente de creación
// + asignación de atletas con sus pruebas objetivo.
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarRange, Plus, Trash2, UserPlus, Flag, PlayCircle, PauseCircle, X } from 'lucide-react'
import { api } from '../../lib/api'
import type { Plan } from '../../lib/types'
import { SPECIALTY_LABEL, PLAN_STATUS_META } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { useIsOwner } from '../../hooks/useSession'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, Chip, EmptyState, IconButton, Spinner } from '../../components/ui/primitives'
import { PlanWizard } from './PlanWizard'
import { AssignAthleteModal } from './AssignAthleteModal'

export function PlansPage() {
  const [showWizard, setShowWizard] = useState(false)
  const [assignTo, setAssignTo] = useState<Plan | null>(null)
  const queryClient = useQueryClient()
  // Borrar un macro es de dueño (R4): el backend ya lo niega al asistente.
  const isOwner = useIsOwner()

  const { data: plans, isLoading } = useQuery({ queryKey: ['plans'], queryFn: api.plans.list })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['plans'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }
  const removePlan = useMutation({
    mutationFn: (id: number) => api.plans.remove(id),
    onSuccess: invalidate,
  })
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.plans.update(id, { status }),
    onSuccess: invalidate,
  })
  const removeAthlete = useMutation({
    mutationFn: ({ planId, athletePlanId }: { planId: number; athletePlanId: number }) =>
      api.plans.removeAthlete(planId, athletePlanId),
    onSuccess: invalidate,
  })

  const ref = usePageEnter([isLoading, plans?.length])

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Macrociclos"
        subtitle="El macrociclo se define a nivel general y luego se ligan los atletas con sus pruebas"
        actions={
          <button className="btn btn-primary" onClick={() => setShowWizard(true)}>
            <Plus size={14} /> Nuevo macrociclo
          </button>
        }
      />

      {isLoading ? (
        <Spinner />
      ) : !plans?.length ? (
        <EmptyState
          icon={<CalendarRange size={24} />}
          title="Sin macrociclos"
          hint="Crea el primer macrociclo de la temporada: duración, kilometraje, curva de progresión y fases."
          action={<button className="btn btn-primary" onClick={() => setShowWizard(true)}><Plus size={14} /> Crear macrociclo</button>}
        />
      ) : (
        plans.map((plan) => {
          const status = PLAN_STATUS_META[plan.effective_status] ?? PLAN_STATUS_META.draft
          // La mutación es una para todas las tarjetas: se bloquea solo la suya.
          const cambiando = setStatus.isPending && setStatus.variables?.id === plan.id
          return (
            <Card key={plan.id} className="card-hover">
              <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                    <h2 className="display text-[16px] font-bold">{plan.name}</h2>
                    <Chip color={status.color}>{status.label}</Chip>
                    {plan.current_week && (
                      <span className="text-[11px] text-text-dim">
                        Semana {plan.current_week}/{plan.total_weeks}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-[11.5px] text-text-dim">
                    Inicio {plan.start_date} · {plan.total_weeks} semanas · micros de {plan.weeks_per_micro} ·{' '}
                    {plan.total_km} km
                    {plan.main_event && <> · objetivo: <span className="text-text">{plan.main_event}</span></>}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  {/* Reproducir / pausar / añadir persona / papelera: cuatro
                      iconos que se leen solos. El nombre completo sale al dejar
                      el ratón encima y es lo que anuncia un lector de pantalla. */}
                  {plan.status !== 'active' && (
                    <IconButton
                      label={`Activar ${plan.name}`} disabled={cambiando}
                      onClick={() => setStatus.mutate({ id: plan.id, status: 'active' })}
                    >
                      <PlayCircle size={15} className="text-mint" />
                    </IconButton>
                  )}
                  {plan.status !== 'suspended' && (
                    <IconButton
                      label={`Suspender ${plan.name}`} disabled={cambiando}
                      onClick={() => setStatus.mutate({ id: plan.id, status: 'suspended' })}
                    >
                      <PauseCircle size={15} />
                    </IconButton>
                  )}
                  <IconButton label={`Agregar un atleta a ${plan.name}`} onClick={() => setAssignTo(plan)}>
                    <UserPlus size={15} />
                  </IconButton>
                  {isOwner && (
                    <IconButton
                      label={`Eliminar ${plan.name}`} tone="danger"
                      onClick={() => confirm(`¿Eliminar "${plan.name}" y todos sus planes semanales?`) && removePlan.mutate(plan.id)}
                    >
                      <Trash2 size={14} />
                    </IconButton>
                  )}
                </div>
              </div>

              {/* Fases en miniatura */}
              <div className="mt-4 flex h-7 gap-[3px]">
                {plan.phases.map((phase) => (
                  <div
                    key={phase.id}
                    className="flex min-w-0 items-center justify-center overflow-hidden whitespace-nowrap rounded-md px-1 text-[9px] font-bold uppercase tracking-wider"
                    style={{
                      flex: phase.week_end - phase.week_start + 1,
                      color: phase.color, background: `${phase.color}16`,
                      border: `1px solid ${phase.color}2e`,
                    }}
                    title={`${phase.name}: S${phase.week_start}–S${phase.week_end}`}
                  >
                    {phase.name}
                  </div>
                ))}
              </div>

              {plan.competitions.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-3">
                  {plan.competitions.map((comp) => (
                    <span key={comp.id} className="flex items-center gap-1.5 text-[10.5px] text-text-dim">
                      <Flag size={11} className={comp.is_main ? 'text-amber' : 'text-text-faint'} />
                      {comp.name} · S{comp.week_number}
                    </span>
                  ))}
                </div>
              )}

              {plan.athletes.length > 0 && (
                <div className="mt-4 border-t border-line pt-3.5">
                  <p className="card-title mb-2.5">Atletas asignados · {plan.athletes.length}</p>
                  <div className="flex flex-wrap gap-2">
                    {plan.athletes.map((ap) => (
                      <div
                        key={ap.id}
                        className="group flex items-center gap-2.5 rounded-xl border border-line bg-surface-2 py-1.5 pl-3 pr-2"
                      >
                        <div>
                          <p className="text-[11.5px] font-semibold leading-tight">{ap.swimmer_name}</p>
                          <p className="text-[9.5px] text-text-dim">
                            {SPECIALTY_LABEL[ap.specialty] ?? ap.specialty}
                            {ap.aerobic_base != null && <> · base {toClock(ap.aerobic_base)}/100</>}
                            {' · '}{ap.events.length} prueba{ap.events.length !== 1 ? 's' : ''}
                          </p>
                        </div>
                        <button
                          className="reveal rounded-md p-1.5 text-text-faint transition-colors hover:bg-surface-3 hover:text-coral"
                          title={`Quitar a ${ap.swimmer_name}`}
                          onClick={() =>
                            confirm(`¿Quitar a ${ap.swimmer_name} del macrociclo?`) &&
                            removeAthlete.mutate({ planId: plan.id, athletePlanId: ap.id })
                          }
                          aria-label={`Quitar a ${ap.swimmer_name}`}
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          )
        })
      )}

      <PlanWizard open={showWizard} onClose={() => setShowWizard(false)} />
      <AssignAthleteModal plan={assignTo} onClose={() => setAssignTo(null)} />
    </div>
  )
}
