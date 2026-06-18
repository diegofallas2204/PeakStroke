// Selector global del macrociclo de trabajo.
// Muestra el perfil completo del macrociclo seleccionado y la lista de todos los
// macrociclos del entrenador —activos, completados, inactivos o suspendidos—,
// permitiendo cambiar cuál se está visualizando y ajustar su estado de ciclo de vida.
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CalendarRange, Check, CheckCircle2, PauseCircle, PlayCircle, Users,
} from 'lucide-react'
import { api } from '../../lib/api'
import type { Plan } from '../../lib/types'
import { CURVE_LABEL, PLAN_STATUS_META } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { Modal } from '../../components/ui/primitives'
import { useSelectedPlanId, setSelectedPlan } from '../../hooks/useSelectedPlan'

function StatusChip({ status }: { status: string }) {
  const meta = PLAN_STATUS_META[status] ?? PLAN_STATUS_META.draft
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10.5px] font-semibold"
      style={{ color: meta.color, background: meta.bg }}
    >
      <span className="size-1.5 rounded-full" style={{ background: meta.color }} />
      {meta.label}
    </span>
  )
}

function ProfileRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-2 last:border-0">
      <span className="text-[10.5px] uppercase tracking-[0.1em] text-text-faint">{label}</span>
      <span className="text-right text-[12.5px] font-medium">{value}</span>
    </div>
  )
}

export function MacroSwitcherModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const selectedId = useSelectedPlanId()
  const queryClient = useQueryClient()
  const { data: plans } = useQuery({ queryKey: ['plans'], queryFn: api.plans.list, enabled: open })

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.plans.update(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const current: Plan | undefined =
    plans?.find((p) => p.id === selectedId) ??
    plans?.find((p) => p.effective_status === 'active') ??
    plans?.[0]

  return (
    <Modal open={open} onClose={onClose} title="Macrociclo de trabajo" wide>
      {!plans?.length ? (
        <p className="py-8 text-center text-sm text-text-dim">
          Aún no hay macrociclos. Crea uno en la sección Macrociclos.
        </p>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)_300px] gap-6">
          {/* Perfil del macrociclo seleccionado */}
          <section>
            {current && (
              <>
                <div className="mb-3 flex items-center gap-3">
                  <h3 className="display text-[17px] font-bold">{current.name}</h3>
                  <StatusChip status={current.effective_status} />
                </div>
                <div className="card p-4">
                  <ProfileRow label="Inicio" value={current.start_date} />
                  <ProfileRow
                    label="Semana actual"
                    value={`${current.current_week ?? '—'} / ${current.total_weeks}`}
                  />
                  <ProfileRow label="Microciclos" value={`cada ${current.weeks_per_micro} semanas`} />
                  <ProfileRow label="Kilometraje total" value={`${current.total_km} km`} />
                  <ProfileRow label="Curva" value={CURVE_LABEL[current.progression_curve] ?? current.progression_curve} />
                  <ProfileRow label="Evento principal" value={current.main_event ?? '—'} />
                  <ProfileRow
                    label="Atletas"
                    value={<span className="inline-flex items-center gap-1.5"><Users size={12} /> {current.athletes.length}</span>}
                  />
                  <ProfileRow label="Fases" value={current.phases.map((p) => p.name).join(' · ') || '—'} />
                </div>
                {current.notes && (
                  <p className="mt-3 rounded-xl border border-line bg-surface-2 p-3 text-[11.5px] text-text-dim">
                    {current.notes}
                  </p>
                )}

                {/* Acciones de ciclo de vida (se guardan en el servidor) */}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    className="btn btn-ghost !py-1.5 text-[11.5px]"
                    disabled={current.status === 'active' || setStatus.isPending}
                    onClick={() => setStatus.mutate({ id: current.id, status: 'active' })}
                  >
                    <PlayCircle size={13} /> Activar
                  </button>
                  <button
                    className="btn btn-ghost !py-1.5 text-[11.5px]"
                    disabled={current.status === 'finished' || setStatus.isPending}
                    onClick={() => setStatus.mutate({ id: current.id, status: 'finished' })}
                  >
                    <CheckCircle2 size={13} /> Marcar completado
                  </button>
                  <button
                    className="btn btn-ghost !py-1.5 text-[11.5px]"
                    disabled={current.status === 'suspended' || setStatus.isPending}
                    onClick={() => setStatus.mutate({ id: current.id, status: 'suspended' })}
                  >
                    <PauseCircle size={13} /> Suspender
                  </button>
                </div>
              </>
            )}
          </section>

          {/* Lista de todos los macrociclos: cambiar el que se visualiza */}
          <section className="flex flex-col gap-2">
            <p className="card-title mb-1">Cambiar a otro · {plans.length}</p>
            <div className="flex flex-col gap-2 overflow-y-auto pr-1" style={{ maxHeight: '62vh' }}>
              {plans.map((plan) => {
                const isCurrent = plan.id === current?.id
                return (
                  <button
                    key={plan.id}
                    onClick={() => setSelectedPlan(plan.id)}
                    className={`group rounded-xl border px-3 py-2.5 text-left transition-all duration-200 ${
                      isCurrent
                        ? 'border-[rgba(59,130,246,.45)] bg-[rgba(59,130,246,.1)]'
                        : 'border-line hover:border-line-strong hover:bg-surface-2'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-1.5 text-[12.5px] font-semibold">
                        <CalendarRange size={13} className="text-text-faint" />
                        {plan.name}
                      </span>
                      {isCurrent && <Check size={14} className="text-accent-soft" />}
                    </div>
                    <div className="mt-1.5 flex items-center justify-between gap-2">
                      <StatusChip status={plan.effective_status} />
                      <span className="mono text-[10px] text-text-faint">
                        {plan.current_week ?? '—'}/{plan.total_weeks}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          </section>
        </div>
      )}
    </Modal>
  )
}
