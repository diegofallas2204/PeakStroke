// Plan semanal: tabla central del sistema con edición inline del tiempo real,
// parones (semanas deshabilitadas) y panel de zonas por semana.
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListChecks, Flag, PauseCircle, PlayCircle } from 'lucide-react'
import { api } from '../../lib/api'
import type { Week } from '../../lib/types'
import { STROKE_LABEL } from '../../lib/constants'
import { toClock, tryToSeconds, signed } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { useSimpleMode } from '../../hooks/useSimpleMode'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, EmptyState, Spinner, StatusBadge } from '../../components/ui/primitives'
import { EventPicker, type EventSelection } from '../../components/ui/EventPicker'
import { ProgressionChart } from '../../components/charts/ProgressionChart'
import { ZonePanel } from './ZonePanel'

function RealTimeCell({
  week, onSave,
}: { week: Week; onSave: (weekId: number, value: number | null) => void }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')

  if (week.disabled) return <span className="text-text-faint">—</span>

  if (!editing) {
    return (
      <button
        className="mono -mx-2 rounded-md px-2 py-1 text-left transition-colors hover:bg-surface-3"
        onClick={() => { setValue(week.real_time != null ? toClock(week.real_time) : ''); setEditing(true) }}
        title="Click para registrar el tiempo real"
      >
        {week.real_time != null
          ? <span className="font-semibold text-mint">{toClock(week.real_time)}</span>
          : <span className="text-text-faint">+ registrar</span>}
      </button>
    )
  }
  const commit = () => {
    const seconds = value.trim() === '' ? null : tryToSeconds(value)
    if (value.trim() !== '' && seconds == null) return
    onSave(week.id, seconds)
    setEditing(false)
  }
  return (
    <input
      autoFocus
      className="field mono !w-24 !px-2 !py-1"
      value={value}
      placeholder="1:05.20"
      onChange={(e) => setValue(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') commit()
        if (e.key === 'Escape') setEditing(false)
      }}
    />
  )
}

export function WeeklyPlanPage() {
  const [selection, setSelection] = useState<EventSelection | null>(null)
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null)
  const queryClient = useQueryClient()

  const { data: weeks, isLoading } = useQuery({
    queryKey: ['weeks', selection?.event.id],
    queryFn: () => api.plans.eventWeeks(selection!.event.id),
    enabled: selection != null,
  })

  const updateWeek = useMutation({
    mutationFn: ({ weekId, body }: { weekId: number; body: unknown }) =>
      api.plans.updateWeek(weekId, body),
    onSuccess: (data) => {
      queryClient.setQueryData(['weeks', selection?.event.id], data)
      // El tiempo real afecta dashboard (estado/progresión) y la tabla del equipo.
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['team-week'] })
    },
  })

  const saveReal = (weekId: number, seconds: number | null) =>
    updateWeek.mutate({
      weekId,
      body: seconds == null ? { clear_real_time: true } : { real_time: seconds },
    })

  const togglePause = (week: Week) => {
    const reason = !week.disabled
      ? prompt('Motivo del parón (lesión, vacaciones…):', week.disable_reason ?? '') ?? undefined
      : undefined
    if (!week.disabled && reason === undefined) return
    updateWeek.mutate({
      weekId: week.id,
      body: { disabled: !week.disabled, disable_reason: reason || null },
    })
  }

  const focusWeek = useMemo(() => {
    if (!weeks) return null
    return weeks.find((w) => w.week_number === selectedWeek)
      ?? weeks.find((w) => w.week_number === selection?.plan.current_week)
      ?? weeks[0]
  }, [weeks, selectedWeek, selection])

  const [simple] = useSimpleMode()
  const ref = usePageEnter([selection?.event.id, isLoading])

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Plan semanal"
        subtitle="Proyección del motor semana a semana: registra el tiempo real para recalcular la curva restante"
      />
      <EventPicker onChange={setSelection} />

      {!selection ? (
        <EmptyState icon={<ListChecks size={24} />} title="Sin datos para mostrar"
          hint="Crea un macrociclo y asigna atletas con sus pruebas para generar el plan." />
      ) : isLoading || !weeks ? (
        <Spinner />
      ) : (
        <>
          {!simple && (
            <div className="grid grid-cols-[1fr_290px] gap-4">
              <Card
                title={`Progresión · ${selection.event.distance}m ${STROKE_LABEL[selection.event.stroke]} · ${selection.athlete.swimmer_name}`}
                className="card-hover"
              >
                <ProgressionChart
                  weeks={weeks}
                  goalTime={selection.event.goal_time}
                  currentWeek={selection.plan.current_week}
                />
                <div className="mt-2 flex gap-5 text-[10.5px] text-text-dim">
                  <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded bg-accent" /> Plan ideal</span>
                  <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded border-t-2 border-dashed border-cyan" /> Proyección ajustada</span>
                  <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-mint" /> Tiempo real</span>
                </div>
              </Card>
              <ZonePanel week={focusWeek} specialty={selection.athlete.specialty} />
            </div>
          )}

          <Card
            title={simple ? 'Plan semanal' : 'Plan generado por el motor · click en una fila para ver sus zonas'}
            className="card-hover"
            flush
          >
            <div className="overflow-x-auto">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Semana</th><th>Fase</th><th>Km</th><th>Esperado</th>
                    {!simple && <th>Pace /100</th>}
                    {!simple && <th>Proyección</th>}
                    <th>Real</th>
                    {!simple && <th>Diferencia</th>}
                    <th>Estado</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  {weeks.map((week) => {
                    const isCurrent = week.week_number === selection.plan.current_week
                    const isFocus = week.week_number === focusWeek?.week_number
                    return (
                      <tr
                        key={week.id}
                        onClick={() => setSelectedWeek(week.week_number)}
                        className="cursor-pointer"
                        style={{
                          background: isFocus ? 'rgba(59,130,246,.08)' : isCurrent ? 'rgba(34,211,238,.05)' : undefined,
                          opacity: week.disabled ? 0.45 : 1,
                        }}
                      >
                        <td>
                          <div className="flex items-center gap-2">
                            <span className="mono text-text-dim">S{week.week_number}</span>
                            <span className="mono font-semibold">{week.date_label}</span>
                            {isCurrent && <span className="pulse-dot size-1.5 rounded-full bg-cyan" />}
                            {week.is_competition && <Flag size={11} className="text-amber" />}
                          </div>
                        </td>
                        <td className="text-text-dim">{week.phase}{week.disabled && ` · ${week.disable_reason ?? 'parón'}`}</td>
                        <td className="mono">{week.planned_km}</td>
                        <td className="mono">{toClock(week.expected_time)}</td>
                        {!simple && (
                          <td className="mono font-semibold text-accent-soft">{toClock(week.pace_100m)}</td>
                        )}
                        {!simple && (
                          <td className="mono text-text-dim">
                            {week.recalc_time != null
                              ? <span className="text-cyan">{toClock(week.recalc_time)}</span>
                              : '—'}
                          </td>
                        )}
                        <td onClick={(e) => e.stopPropagation()}>
                          <RealTimeCell week={week} onSave={saveReal} />
                        </td>
                        {!simple && (
                          <td className="mono" style={{ color: week.diff_seconds == null ? '#565e82' : week.diff_seconds <= 0 ? '#34d399' : '#fb7185' }}>
                            {week.diff_seconds != null ? `${signed(week.diff_seconds)}s` : '—'}
                          </td>
                        )}
                        <td>{week.real_time != null ? <StatusBadge status={week.status} /> : <span className="text-[10.5px] text-text-faint">—</span>}</td>
                        <td onClick={(e) => e.stopPropagation()}>
                          <button
                            className="btn btn-ghost !p-1.5"
                            onClick={() => togglePause(week)}
                            title={week.disabled ? 'Reactivar semana' : 'Marcar parón (lesión/vacaciones)'}
                          >
                            {week.disabled ? <PlayCircle size={13} className="text-mint" /> : <PauseCircle size={13} className="text-text-dim" />}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
