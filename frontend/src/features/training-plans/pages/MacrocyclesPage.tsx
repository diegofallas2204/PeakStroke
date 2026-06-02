/**
 * MacrocyclesPage.tsx — Lista de macrociclos del entrenador.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMacrocycles, useDeleteMacrocycle } from '../hooks/useMacrocycles'
import { MacrocycleWizard } from '../components/MacrocycleWizard'
import { format, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'

export function MacrocyclesPage() {
  const [showWizard, setShowWizard] = useState(false)
  const { data: macrocycles = [], isLoading } = useMacrocycles()
  const deleteMacrocycle = useDeleteMacrocycle()
  const navigate = useNavigate()

  const STATUS_LABELS: Record<string, { label: string; color: string }> = {
    active: { label: 'Activo', color: 'text-green-400' },
    draft: { label: 'Borrador', color: 'text-yellow-400' },
    finished: { label: 'Finalizado', color: 'text-gray-400' },
  }

  return (
    <div className="min-h-screen bg-slate-950 p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white">Macrociclos</h1>
          <p className="text-gray-400 mt-1">Planificación de temporadas</p>
        </div>
        <button className="btn-primary" onClick={() => setShowWizard(true)}>
          + Nuevo macrociclo
        </button>
      </div>

      {isLoading ? (
        <div className="text-gray-400 text-center py-20">Cargando...</div>
      ) : macrocycles.length === 0 ? (
        <div className="text-center py-20 space-y-4">
          <div className="text-6xl">🏊</div>
          <p className="text-white text-xl font-medium">Sin macrociclos aún</p>
          <p className="text-gray-400">Crea tu primer macrociclo para comenzar a planificar</p>
          <button className="btn-primary" onClick={() => setShowWizard(true)}>
            Crear primer macrociclo
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {macrocycles.map(macro => {
            const status = STATUS_LABELS[macro.status] ?? STATUS_LABELS.active
            return (
              <div
                key={macro.id}
                className="bg-slate-900 border border-white/10 rounded-xl p-5 hover:border-sky-500/50 transition-colors cursor-pointer"
                onClick={() => navigate(`/macrocycles/${macro.id}`)}
              >
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <h3 className="text-white text-lg font-semibold">{macro.name}</h3>
                    <div className="flex items-center gap-4 text-sm text-gray-400">
                      <span>
                        {format(parseISO(macro.start_date), 'dd MMM yyyy', { locale: es })} →{' '}
                        {format(parseISO(macro.end_date), 'dd MMM yyyy', { locale: es })}
                      </span>
                      <span>·</span>
                      <span>{macro.total_weeks} semanas</span>
                      <span>·</span>
                      <span>{macro.total_km} km</span>
                      <span>·</span>
                      <span>{macro.swimmer_count ?? 0} atletas</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-medium ${status.color}`}>{status.label}</span>
                    <button
                      className="text-gray-600 hover:text-red-400 transition-colors p-1"
                      onClick={e => {
                        e.stopPropagation()
                        if (confirm('¿Eliminar este macrociclo y todos sus datos?')) {
                          deleteMacrocycle.mutate(macro.id)
                        }
                      }}
                    >
                      🗑
                    </button>
                  </div>
                </div>

                {/* Fases */}
                {macro.phases.length > 0 && (
                  <div className="mt-3 flex gap-1">
                    {macro.phases.map(phase => (
                      <div
                        key={phase.id}
                        className="flex-1 h-1.5 rounded-full"
                        style={{ backgroundColor: phase.color ?? '#64748b' }}
                        title={`${phase.name}: semanas ${phase.week_start}–${phase.week_end}`}
                      />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {showWizard && <MacrocycleWizard onClose={() => setShowWizard(false)} />}
    </div>
  )
}
