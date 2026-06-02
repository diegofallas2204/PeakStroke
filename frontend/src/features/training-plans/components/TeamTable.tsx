/**
 * TeamTable.tsx — Tabla del equipo: vista operativa semanal.
 *
 * Una fila por atleta × prueba.
 * Selector inline de prueba por atleta (cambia los tiempos de esa fila).
 * Columnas: Atleta | Prueba | Semana | km | pace/100m | R1 | R2 | MVO2 | RL | V | Esperado | Real | Δ | Estado
 * Zonas colapsables con un toggle.
 */
import { useState } from 'react'
import { format, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'
import { useTeamTable, useUpdateWeek } from '../hooks/useMacrocycles'
import type { TeamRow, WeeklyPlan } from '../api'
import { formatTime, formatPace } from '../utils/timeFormat'

interface Props {
  macroId: number
  totalWeeks: number
}

export function TeamTable({ macroId, totalWeeks }: Props) {
  const [currentWeek, setCurrentWeek] = useState(1)
  const [zonesExpanded, setZonesExpanded] = useState(true)
  const [editingWeek, setEditingWeek] = useState<number | null>(null)
  const [realTimeInput, setRealTimeInput] = useState('')

  const { data: rows = [], isLoading } = useTeamTable(macroId, currentWeek)
  const updateWeek = useUpdateWeek(macroId)

  // Agrupar filas por atleta para poder cambiar la prueba activa por atleta
  const athleteRows = rows.reduce<Record<number, TeamRow[]>>((acc, row) => {
    const key = row.swimmer_id
    if (!acc[key]) acc[key] = []
    acc[key].push(row)
    return acc
  }, {})

  function statusBadge(week: WeeklyPlan) {
    if (week.disabled) return <span className="badge-gray">Inhabilitada</span>
    if (!week.real_time || !week.expected_time) return null
    const delta = week.real_time - week.expected_time
    const pct = (delta / week.expected_time) * 100
    if (pct < -2) return <span className="badge-green">Adelantado</span>
    if (pct > 5) return <span className="badge-red">Atrasado</span>
    return <span className="badge-yellow">En plan</span>
  }

  async function handleToggleDisable(week: WeeklyPlan, reason: 'lesion' | 'vacaciones' | 'otro') {
    await updateWeek.mutateAsync({
      weekId: week.id,
      data: { disabled: !week.disabled, disable_reason: !week.disabled ? reason : null },
    })
  }

  async function handleSaveRealTime(weekId: number) {
    const seconds = parseTimeInput(realTimeInput)
    if (seconds === null) return
    await updateWeek.mutateAsync({ weekId, data: { real_time: seconds } })
    setEditingWeek(null)
    setRealTimeInput('')
  }

  return (
    <div className="space-y-4">
      {/* Navegación de semana */}
      <div className="flex items-center gap-3">
        <button
          className="btn-secondary"
          onClick={() => setCurrentWeek(w => Math.max(1, w - 1))}
          disabled={currentWeek === 1}
        >←</button>
        <span className="font-semibold text-white">Semana {currentWeek} / {totalWeeks}</span>
        <button
          className="btn-secondary"
          onClick={() => setCurrentWeek(w => Math.min(totalWeeks, w + 1))}
          disabled={currentWeek === totalWeeks}
        >→</button>

        <button
          className="ml-auto btn-ghost text-sm"
          onClick={() => setZonesExpanded(z => !z)}
        >
          {zonesExpanded ? '⊟ Colapsar zonas' : '⊞ Expandir zonas'}
        </button>
      </div>

      {isLoading ? (
        <div className="text-gray-400 py-8 text-center">Cargando...</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-800 text-gray-300 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 sticky left-0 bg-slate-800">Atleta</th>
                <th className="px-4 py-3">Prueba</th>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3">km Plan</th>
                <th className="px-4 py-3">pace/100m</th>
                {zonesExpanded && (
                  <>
                    <th className="px-3 py-3 text-blue-400">R1</th>
                    <th className="px-3 py-3 text-emerald-400">R2</th>
                    <th className="px-3 py-3 text-yellow-400">MVO2</th>
                    <th className="px-3 py-3 text-orange-400">RL</th>
                    <th className="px-3 py-3 text-red-400">V</th>
                  </>
                )}
                <th className="px-4 py-3">Esperado</th>
                <th className="px-4 py-3">Real</th>
                <th className="px-4 py-3">Δ</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {Object.entries(athleteRows).map(([swimmerId, athleteRowList]) => {
                const [activeEventId, setActiveEventId] = useState<number>(
                  athleteRowList[0]?.event.id
                )
                const activeRow = athleteRowList.find(r => r.event.id === activeEventId) ?? athleteRowList[0]
                const week = activeRow?.week

                return (
                  <tr key={swimmerId} className="bg-slate-900 hover:bg-slate-800/50 transition-colors">
                    <td className="px-4 py-3 sticky left-0 bg-slate-900 font-medium text-white">
                      {activeRow.swimmer_name}
                    </td>

                    {/* Selector inline de prueba */}
                    <td className="px-4 py-3">
                      <select
                        className="bg-slate-700 text-white text-xs rounded px-2 py-1 border border-white/10"
                        value={activeEventId}
                        onChange={e => setActiveEventId(Number(e.target.value))}
                      >
                        {athleteRowList.map(r => (
                          <option key={r.event.id} value={r.event.id}>
                            {r.event.distance}m {r.event.stroke}
                          </option>
                        ))}
                      </select>
                    </td>

                    <td className="px-4 py-3 text-gray-400">
                      {week?.week_date
                        ? format(parseISO(week.week_date), 'dd/MM', { locale: es })
                        : '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-300">{week?.planned_km ?? '-'}</td>
                    <td className="px-4 py-3 font-mono text-cyan-400">
                      {week?.pace_100m ? formatPace(week.pace_100m) : '-'}
                    </td>

                    {zonesExpanded && week?.zones && (
                      <>
                        <td className="px-3 py-3 font-mono text-blue-400 text-xs">{formatPace(week.zones.r1)}</td>
                        <td className="px-3 py-3 font-mono text-emerald-400 text-xs">{formatPace(week.zones.r2)}</td>
                        <td className="px-3 py-3 font-mono text-yellow-400 text-xs">{formatPace(week.zones.mvo2)}</td>
                        <td className="px-3 py-3 font-mono text-orange-400 text-xs">{formatPace(week.zones.rl)}</td>
                        <td className="px-3 py-3 font-mono text-red-400 text-xs">{formatPace(week.zones.v)}</td>
                      </>
                    )}
                    {zonesExpanded && !week?.zones && (
                      <><td colSpan={5} /></>
                    )}

                    <td className="px-4 py-3 font-mono text-white">
                      {week?.expected_time ? formatTime(week.expected_time) : '-'}
                    </td>

                    {/* Tiempo real — editable inline */}
                    <td className="px-4 py-3 font-mono">
                      {editingWeek === week?.id ? (
                        <div className="flex gap-1">
                          <input
                            className="w-24 bg-slate-700 text-white rounded px-2 py-1 text-xs font-mono border border-sky-500"
                            placeholder="m:ss.cc"
                            value={realTimeInput}
                            onChange={e => setRealTimeInput(e.target.value)}
                            onKeyDown={e => {
                              if (e.key === 'Enter') handleSaveRealTime(week!.id)
                              if (e.key === 'Escape') setEditingWeek(null)
                            }}
                            autoFocus
                          />
                          <button className="text-green-400 text-xs" onClick={() => handleSaveRealTime(week!.id)}>✓</button>
                          <button className="text-gray-400 text-xs" onClick={() => setEditingWeek(null)}>✗</button>
                        </div>
                      ) : (
                        <button
                          className="text-gray-300 hover:text-white"
                          onClick={() => {
                            setEditingWeek(week?.id ?? null)
                            setRealTimeInput(week?.real_time ? formatTime(week.real_time) : '')
                          }}
                        >
                          {week?.real_time ? formatTime(week.real_time) : <span className="text-gray-600">— ingresar</span>}
                        </button>
                      )}
                    </td>

                    {/* Delta */}
                    <td className="px-4 py-3 font-mono">
                      {week?.real_time && week?.expected_time
                        ? <DeltaBadge real={week.real_time} expected={week.expected_time} />
                        : '-'}
                    </td>

                    <td className="px-4 py-3">{week ? statusBadge(week) : null}</td>

                    {/* Acciones: inhabilitar semana */}
                    <td className="px-4 py-3">
                      {week && (
                        <button
                          className={`text-xs ${week.disabled ? 'text-green-400 hover:text-green-300' : 'text-gray-500 hover:text-red-400'}`}
                          onClick={() => handleToggleDisable(week, 'lesion')}
                          title={week.disabled ? 'Rehabilitar semana' : 'Inhabilitar semana'}
                        >
                          {week.disabled ? '▶ Activar' : '⏸ Parón'}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={15} className="text-center py-12 text-gray-500">
                    No hay atletas en este macrociclo. Agrega uno para comenzar.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function DeltaBadge({ real, expected }: { real: number; expected: number }) {
  const delta = real - expected
  const pct = (delta / expected) * 100
  const color = delta < 0 ? 'text-green-400' : delta > 0 ? 'text-red-400' : 'text-gray-400'
  const sign = delta < 0 ? '' : '+'
  return (
    <span className={`font-mono ${color}`}>
      {sign}{delta.toFixed(2)}s
    </span>
  )
}

function parseTimeInput(input: string): number | null {
  input = input.trim().replace(',', '.')
  if (input.includes(':')) {
    const [m, s] = input.split(':')
    const mins = parseInt(m)
    const secs = parseFloat(s)
    if (isNaN(mins) || isNaN(secs)) return null
    return mins * 60 + secs
  }
  const n = parseFloat(input)
  return isNaN(n) ? null : n
}
