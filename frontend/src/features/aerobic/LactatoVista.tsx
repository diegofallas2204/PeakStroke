// La vista «Lactato» de Base aeróbica: historial de tests de lactato del atleta
// y la ficha del elegido. No es una sección del menú (nota 26): es otra forma de
// medir, junto al T-30 y el CSS, y por eso vive en la misma página.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Droplet, Plus, Trash2 } from 'lucide-react'
import { api } from '../../lib/api'
import { ZONE_META } from '../../lib/constants'
import { fechaCorta, toClock } from '../../lib/format'
import { confirmar } from '../../lib/confirmar'
import { Card, EmptyState, Spinner } from '../../components/ui/primitives'
import { ErrorDeCarga } from '../../components/ui/ErrorDeCarga'
import { LactatoDetalle } from './LactatoDetalle'

export function LactatoVista({
  swimmerId, menor, puedeApuntar, seleccionado, onSeleccionar, onNuevo,
}: {
  swimmerId: number
  menor: boolean
  puedeApuntar: boolean
  seleccionado: number | null
  onSeleccionar: (id: number) => void
  onNuevo: () => void
}) {
  const queryClient = useQueryClient()
  const { data: tests, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['lactate', swimmerId],
    queryFn: () => api.lactate.list(swimmerId),
  })
  const quitar = useMutation({
    mutationFn: (id: number) => api.lactate.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['lactate'] }),
  })

  if (isLoading) return <Spinner />
  if (isError) {
    return <ErrorDeCarga error={error} que="los tests de lactato" onReintentar={() => void refetch()} reintentando={isFetching} />
  }
  if (!tests?.length) {
    return (
      <EmptyState
        icon={<Droplet size={24} />}
        title="Sin tests de lactato"
        hint="Una serie a ritmo constante con lactato, FC, esfuerzo y brazadas por repetición: dice si la zona que se prescribe es la que el atleta produce."
        action={puedeApuntar && (
          <button className="btn btn-primary" onClick={onNuevo}><Plus size={14} /> Test de lactato</button>
        )}
      />
    )
  }

  const test = tests.find((t) => t.id === seleccionado) ?? tests[0]
  return (
    <div className="grid items-start gap-4 [&>*]:min-w-0 lg:grid-cols-[300px_1fr]">
      <Card title="Historial" className="card-hover self-start !p-2.5">
        <div className="flex flex-col gap-1.5">
          {tests.map((t) => {
            const activo = t.id === test.id
            const zona = ZONE_META[t.target_zone]
            return (
              <div
                key={t.id}
                className={`group flex items-center gap-1 rounded-xl border pr-1.5 transition-all duration-200 ${
                  activo ? 'border-[rgba(251,113,133,.45)] bg-[rgba(251,113,133,.08)]' : 'border-transparent hover:bg-surface-2'
                }`}
              >
                <button
                  onClick={() => onSeleccionar(t.id)} aria-pressed={activo}
                  className="flex min-w-0 flex-1 items-center justify-between rounded-xl py-2.5 pl-3 pr-1 text-left"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[12px] font-bold" style={{ color: zona?.color }}>{t.target_zone}</span>
                      <span className="text-[10px] text-text-dim">{t.reps.length}×{t.rep_distance}</span>
                    </div>
                    <p className="mt-0.5 text-[10px] text-text-faint">{fechaCorta(t.test_date)}</p>
                  </div>
                  <div className="text-right">
                    <p className="mono text-[12.5px] font-bold">{toClock(t.summary.mean_time, 1)}</p>
                    {t.summary.lactate_median != null && (
                      <p className="text-[9.5px] text-text-dim">{t.summary.lactate_median} mmol/L</p>
                    )}
                  </div>
                </button>
                {puedeApuntar && (
                  <button
                    type="button"
                    className="reveal shrink-0 rounded-md p-1.5 text-text-faint transition-colors hover:text-coral"
                    aria-label={`Dar de baja el test de lactato del ${fechaCorta(t.test_date)}`}
                    title="Dar de baja"
                    onClick={async () => {
                      if (await confirmar({
                        titulo: '¿Dar de baja este test de lactato?',
                        texto: 'Deja de salir en el historial. La medición no se borra.',
                        accion: 'Dar de baja', peligro: true,
                      })) quitar.mutate(t.id)
                    }}
                  >
                    <Trash2 size={12.5} />
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </Card>
      <LactatoDetalle test={test} menor={menor} />
    </div>
  )
}
