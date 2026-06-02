/**
 * AddAthleteModal.tsx — Modal para agregar un atleta al macrociclo.
 * Flujo: Seleccionar atleta → definir hasta 3 pruebas → base aeróbica → guardar.
 */
import { useState } from 'react'
import { useSwimmers, useAddAthlete, useCreateSwimmer } from '../hooks/useMacrocycles'
import { parseTime, formatTime } from '../utils/timeFormat'

interface EventForm {
  priority: 1 | 2 | 3
  distance: number
  stroke: string
  current_time_str: string
  goal_time_str: string
}

const DISTANCES = [50, 100, 200, 400, 800, 1500]
const STROKES = ['libre', 'espalda', 'mariposa', 'pecho', 'combinado']

export function AddAthleteModal({ macroId, onClose }: { macroId: number; onClose: () => void }) {
  const { data: swimmers = [] } = useSwimmers()
  const addAthlete = useAddAthlete(macroId)
  const createSwimmer = useCreateSwimmer()

  const [step, setStep] = useState<'select' | 'events' | 'aerobic'>('select')
  const [selectedSwimmerId, setSelectedSwimmerId] = useState<number | null>(null)
  const [newSwimmerName, setNewSwimmerName] = useState('')
  const [creatingNew, setCreatingNew] = useState(false)
  const [aerobicBase, setAerobicBase] = useState('')

  const [events, setEvents] = useState<EventForm[]>([
    { priority: 1, distance: 100, stroke: 'libre', current_time_str: '', goal_time_str: '' },
  ])

  function addEvent() {
    if (events.length >= 3) return
    setEvents(e => [...e, {
      priority: (e.length + 1) as 1 | 2 | 3,
      distance: 200, stroke: 'libre', current_time_str: '', goal_time_str: '',
    }])
  }

  async function handleCreateNewSwimmer() {
    if (!newSwimmerName.trim()) return
    const swimmer = await createSwimmer.mutateAsync({ name: newSwimmerName.trim() })
    setSelectedSwimmerId(swimmer.id)
    setCreatingNew(false)
    setStep('events')
  }

  async function handleSubmit() {
    if (!selectedSwimmerId) return
    const parsedEvents = events.map(e => ({
      priority: e.priority,
      distance: e.distance,
      stroke: e.stroke,
      current_time: parseTime(e.current_time_str),
      goal_time: parseTime(e.goal_time_str),
    }))
    const aerobicBaseValue = aerobicBase ? parseTime(aerobicBase) : undefined
    try {
      await addAthlete.mutateAsync({
        swimmer_id: selectedSwimmerId,
        events: parsedEvents as any,
        aerobic_base: aerobicBaseValue ? { value: aerobicBaseValue } : null,
      })
      onClose()
    } catch (e: any) {
      alert(e?.response?.data?.detail ?? 'Error al agregar atleta')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-2xl border border-white/10 w-full max-w-lg p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-white">Agregar atleta al macrociclo</h2>
          <button className="text-gray-400 hover:text-white" onClick={onClose}>✕</button>
        </div>

        {/* Step: Seleccionar atleta */}
        {step === 'select' && (
          <div className="space-y-4">
            <p className="text-gray-400 text-sm">Selecciona un atleta existente o crea uno nuevo</p>

            {!creatingNew ? (
              <>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {swimmers.map(s => (
                    <button key={s.id}
                      className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${selectedSwimmerId === s.id ? 'border-sky-500 bg-sky-500/10 text-white' : 'border-white/10 hover:border-white/20 text-gray-300'}`}
                      onClick={() => setSelectedSwimmerId(s.id)}>
                      <span className="font-medium">{s.name}</span>
                      {s.age && <span className="text-gray-500 text-sm ml-2">({s.age} años)</span>}
                      {s.specialty && <span className="text-gray-500 text-sm ml-2">· {s.specialty}</span>}
                    </button>
                  ))}
                </div>
                <button className="text-sky-400 text-sm hover:text-sky-300" onClick={() => setCreatingNew(true)}>
                  + Crear nuevo atleta
                </button>
                <button className="btn-primary w-full" disabled={!selectedSwimmerId}
                  onClick={() => setStep('events')}>
                  Siguiente →
                </button>
              </>
            ) : (
              <div className="space-y-3">
                <input className="input" placeholder="Nombre del atleta" value={newSwimmerName}
                  onChange={e => setNewSwimmerName(e.target.value)} autoFocus />
                <div className="flex gap-3">
                  <button className="btn-secondary flex-1" onClick={() => setCreatingNew(false)}>Cancelar</button>
                  <button className="btn-primary flex-1" onClick={handleCreateNewSwimmer}
                    disabled={!newSwimmerName.trim() || createSwimmer.isPending}>
                    Crear y continuar
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step: Pruebas */}
        {step === 'events' && (
          <div className="space-y-4">
            <p className="text-gray-400 text-sm">Define hasta 3 pruebas (tiempo en formato m:ss.cc)</p>

            {events.map((ev, idx) => (
              <div key={idx} className="bg-slate-800 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sky-400 text-sm font-semibold">Prueba #{ev.priority}</span>
                  {idx > 0 && (
                    <button className="text-gray-600 hover:text-red-400 text-xs"
                      onClick={() => setEvents(e => e.filter((_, i) => i !== idx))}>
                      ✕ Quitar
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label text-xs">Distancia</label>
                    <select className="input text-sm" value={ev.distance}
                      onChange={e => setEvents(es => es.map((ev2, i) => i === idx ? { ...ev2, distance: Number(e.target.value) } : ev2))}>
                      {DISTANCES.map(d => <option key={d} value={d}>{d}m</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="label text-xs">Estilo</label>
                    <select className="input text-sm" value={ev.stroke}
                      onChange={e => setEvents(es => es.map((ev2, i) => i === idx ? { ...ev2, stroke: e.target.value } : ev2))}>
                      {STROKES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label text-xs">Tiempo actual</label>
                    <input className="input text-sm font-mono" placeholder="1:05.30" value={ev.current_time_str}
                      onChange={e => setEvents(es => es.map((ev2, i) => i === idx ? { ...ev2, current_time_str: e.target.value } : ev2))} />
                  </div>
                  <div>
                    <label className="label text-xs">Tiempo meta</label>
                    <input className="input text-sm font-mono" placeholder="1:02.00" value={ev.goal_time_str}
                      onChange={e => setEvents(es => es.map((ev2, i) => i === idx ? { ...ev2, goal_time_str: e.target.value } : ev2))} />
                  </div>
                </div>
              </div>
            ))}

            {events.length < 3 && (
              <button className="text-sky-400 text-sm hover:text-sky-300" onClick={addEvent}>
                + Agregar prueba secundaria
              </button>
            )}

            <div className="flex gap-3">
              <button className="btn-secondary flex-1" onClick={() => setStep('select')}>← Atrás</button>
              <button className="btn-primary flex-1"
                disabled={events.some(e => !e.current_time_str || !e.goal_time_str)}
                onClick={() => setStep('aerobic')}>
                Siguiente →
              </button>
            </div>
          </div>
        )}

        {/* Step: Base aeróbica */}
        {step === 'aerobic' && (
          <div className="space-y-4">
            <p className="text-gray-400 text-sm">
              Base aeróbica = promedio pace/100m del test T-30 o T-15 (opcional — se puede ingresar después)
            </p>
            <div>
              <label className="label">pace /100m en R1 (mm:ss.cc)</label>
              <input className="input font-mono" placeholder="1:23.50 — dejar vacío si no hay test aún"
                value={aerobicBase} onChange={e => setAerobicBase(e.target.value)} />
            </div>
            <p className="text-xs text-gray-500">
              Si dejas este campo vacío, podrás registrar el test T-30/T-15 completo desde la ficha del atleta y vincularlo al macrociclo.
            </p>
            <div className="flex gap-3">
              <button className="btn-secondary flex-1" onClick={() => setStep('events')}>← Atrás</button>
              <button className="btn-primary flex-1" onClick={handleSubmit} disabled={addAthlete.isPending}>
                {addAthlete.isPending ? 'Guardando...' : 'Agregar atleta y generar plan'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
