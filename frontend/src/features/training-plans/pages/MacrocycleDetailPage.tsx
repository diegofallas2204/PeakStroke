/**
 * MacrocycleDetailPage.tsx — Vista detallada de un macrociclo.
 * Muestra: info del macro, tabla del equipo y botón para agregar atletas.
 */
import { useParams } from 'react-router-dom'
import { useMacrocycle } from '../hooks/useMacrocycles'
import { TeamTable } from '../components/TeamTable'
import { useState } from 'react'
import { AddAthleteModal } from '../components/AddAthleteModal'

export function MacrocycleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const macroId = Number(id)
  const { data: macro, isLoading } = useMacrocycle(macroId)
  const [showAddAthlete, setShowAddAthlete] = useState(false)

  if (isLoading) return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-gray-400">Cargando...</div>
  if (!macro) return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-red-400">Macrociclo no encontrado</div>

  return (
    <div className="min-h-screen bg-slate-950 p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{macro.name}</h1>
          <p className="text-gray-400 text-sm">
            {macro.total_weeks} semanas · {macro.total_km} km · Curva {macro.progression_curve}
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowAddAthlete(true)}>
          + Agregar atleta
        </button>
      </div>

      {/* Fases del macrociclo */}
      {macro.phases && macro.phases.length > 0 && (
        <div className="flex gap-2">
          {macro.phases.map(phase => (
            <div key={phase.id}
              className="flex-1 rounded-lg p-2 text-center text-xs font-medium"
              style={{ backgroundColor: `${phase.color}22`, borderColor: phase.color ?? '#64748b', border: '1px solid' }}>
              <p style={{ color: phase.color ?? '#94a3b8' }}>{phase.name}</p>
              <p className="text-gray-500 mt-0.5">S{phase.week_start}–S{phase.week_end}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabla del equipo */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">Tabla del equipo</h2>
        <TeamTable macroId={macroId} totalWeeks={macro.total_weeks} />
      </div>

      {showAddAthlete && (
        <AddAthleteModal macroId={macroId} onClose={() => setShowAddAthlete(false)} />
      )}
    </div>
  )
}
