// La lista de sesiones del rango, con corregir y borrar.
//
// El borrado es REAL —la sesión es la excepción a «nada se borra»: es un
// registro que su dueño corrige— y por eso se confirma diciendo qué pasa
// después: la carga se recalcula desde lo que quede.
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Activity, Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '../../lib/api'
import type { TrainingSession } from '../../lib/types'
import { RPE_LABEL } from '../../lib/constants'
import { toClock, toDayMonth, toHoursMinutes } from '../../lib/format'
import { Card, EmptyState } from '../../components/ui/primitives'

export function SessionsCard({
  sessions, onNew, onEdit,
}: {
  sessions: TrainingSession[]
  onNew: () => void
  onEdit: (s: TrainingSession) => void
}) {
  const queryClient = useQueryClient()
  const [error, setError] = useState('')
  const remove = useMutation({
    mutationFn: (id: number) => api.sessions.remove(id),
    onMutate: () => setError(''),
    // Un borrado que falla (otra pestaña ya la borró, o la red) se dice: la fila
    // que sigue ahí sin explicación es peor que el error.
    onError: (e: Error) => setError(`No se pudo borrar la sesión: ${e.message}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      queryClient.invalidateQueries({ queryKey: ['training-load'] })
    },
  })

  const sorted = [...sessions].sort((a, b) => b.session_date.localeCompare(a.session_date))
  const km = sessions.reduce((acc, s) => acc + s.distance_m, 0) / 1000

  return (
    <Card
      title={sessions.length
        ? `Sesiones · ${sessions.length} en el rango · ${km.toFixed(1)} km`
        : 'Sesiones'}
      className="card-hover"
      flush
    >
      {error && <p className="px-5 pb-3 text-xs text-coral">{error}</p>}
      {!sorted.length ? (
        <EmptyState
          icon={<Activity size={24} />}
          title="Sin sesiones en este rango"
          hint="Apunta lo que se nadó cada día: metros, duración y esfuerzo. De ahí sale la carga."
          action={(
            <button className="btn btn-primary" onClick={onNew}>
              <Plus size={14} /> Apuntar sesión
            </button>
          )}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-left text-[12.5px]">
            <thead>
              <tr className="border-y border-line text-[10px] uppercase tracking-wider text-text-faint">
                <th className="px-5 py-2 font-semibold">Fecha</th>
                <th className="px-3 py-2 text-right font-semibold">Metros</th>
                <th className="px-3 py-2 text-right font-semibold">Duración</th>
                <th className="px-3 py-2 text-right font-semibold">Ritmo /100</th>
                <th className="px-3 py-2 font-semibold">RPE</th>
                <th className="px-3 py-2 font-semibold">Notas</th>
                <th className="px-5 py-2" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((s) => (
                <tr key={s.id} className="group border-b border-line last:border-0 hover:bg-surface-2">
                  <td className="whitespace-nowrap px-5 py-2.5 font-semibold">{toDayMonth(s.session_date)}</td>
                  <td className="mono px-3 py-2.5 text-right">{s.distance_m.toLocaleString('es')}</td>
                  <td className="mono px-3 py-2.5 text-right">{toHoursMinutes(s.duration_s)}</td>
                  <td className="mono px-3 py-2.5 text-right text-accent-soft">{toClock(s.pace_100m, 1)}</td>
                  <td className="px-3 py-2.5" title={s.rpe != null ? RPE_LABEL[s.rpe] : undefined}>
                    {s.rpe != null ? <span className="mono font-semibold">{s.rpe}</span> : <span className="text-text-faint">—</span>}
                  </td>
                  <td className="max-w-[260px] truncate px-3 py-2.5 text-text-dim" title={s.notes ?? undefined}>
                    {s.notes ?? ''}
                  </td>
                  <td className="whitespace-nowrap px-5 py-2.5 text-right">
                    <button
                      className="rounded-md p-1.5 text-text-faint transition-colors hover:text-text"
                      aria-label={`Corregir la sesión del ${toDayMonth(s.session_date)}`}
                      onClick={() => onEdit(s)}
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      className="rounded-md p-1.5 text-text-faint transition-colors hover:text-coral"
                      aria-label={`Borrar la sesión del ${toDayMonth(s.session_date)}`}
                      disabled={remove.isPending}
                      onClick={() => {
                        if (confirm('¿Borrar esta sesión? Se borra de verdad y la carga se recalcula sin ella.')) {
                          remove.mutate(s.id)
                        }
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
