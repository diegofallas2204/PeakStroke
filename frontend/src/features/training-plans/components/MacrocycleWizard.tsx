/**
 * MacrocycleWizard.tsx — Wizard de creación de macrociclo.
 * Paso 1: Datos generales (nombre, fechas, semanas, km, curva, sesiones)
 * Paso 2: Fases del macrociclo (configurables)
 * Paso 3: Confirmación
 */
import { useState } from 'react'
import { useCreateMacrocycle } from '../hooks/useMacrocycles'
import { useNavigate } from 'react-router-dom'

const CURVES = [
  { value: 'sigmoid', label: 'Sigmoidal (recomendada)', desc: 'Lento → rápido → lento. Más fisiológico.' },
  { value: 'linear', label: 'Lineal', desc: 'Mejora constante cada semana.' },
  { value: 'logarithmic', label: 'Logarítmica', desc: 'Ganancias rápidas al inicio, se desacelera.' },
  { value: 'exponential', label: 'Exponencial', desc: 'Lento al inicio, se acelera hacia el final.' },
]

interface FormData {
  name: string
  start_date: string
  total_weeks: 12 | 18
  microcycle_weeks: 4 | 5
  sessions_per_week: number
  total_km: number
  progression_curve: string
  notes: string
}

export function MacrocycleWizard({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState<FormData>({
    name: '',
    start_date: '',
    total_weeks: 12,
    microcycle_weeks: 4,
    sessions_per_week: 5,
    total_km: 300,
    progression_curve: 'sigmoid',
    notes: '',
  })

  const createMacrocycle = useCreateMacrocycle()
  const navigate = useNavigate()

  function calcEndDate(startDate: string, weeks: number): string {
    if (!startDate) return ''
    const d = new Date(startDate)
    d.setDate(d.getDate() + weeks * 7)
    return d.toISOString().split('T')[0]
  }

  async function handleSubmit() {
    const endDate = calcEndDate(form.start_date, form.total_weeks)
    try {
      const macro = await createMacrocycle.mutateAsync({
        name: form.name,
        start_date: form.start_date,
        end_date: endDate,
        total_weeks: form.total_weeks,
        microcycle_weeks: form.microcycle_weeks,
        sessions_per_week: form.sessions_per_week,
        total_km: form.total_km,
        progression_curve: form.progression_curve,
        notes: form.notes || undefined,
      })
      onClose()
      navigate(`/macrocycles/${macro.id}`)
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-2xl border border-white/10 w-full max-w-lg p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-white">Nuevo Macrociclo</h2>
          <button className="text-gray-400 hover:text-white" onClick={onClose}>✕</button>
        </div>

        {/* Steps indicator */}
        <div className="flex gap-2">
          {[1, 2].map(s => (
            <div key={s} className={`flex-1 h-1 rounded-full ${s <= step ? 'bg-sky-500' : 'bg-slate-700'}`} />
          ))}
        </div>

        {/* Step 1: Datos generales */}
        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="label">Nombre del macrociclo</label>
              <input
                className="input"
                placeholder="Ej: Temporada 2026 Verano"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Fecha de inicio</label>
                <input type="date" className="input" value={form.start_date}
                  onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div>
                <label className="label">Duración</label>
                <select className="input" value={form.total_weeks}
                  onChange={e => setForm(f => ({ ...f, total_weeks: Number(e.target.value) as 12 | 18 }))}>
                  <option value={12}>12 semanas</option>
                  <option value={18}>18 semanas</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Semanas por microciclo</label>
                <select className="input" value={form.microcycle_weeks}
                  onChange={e => setForm(f => ({ ...f, microcycle_weeks: Number(e.target.value) as 4 | 5 }))}>
                  <option value={4}>4 semanas</option>
                  <option value={5}>5 semanas</option>
                </select>
              </div>
              <div>
                <label className="label">Sesiones por semana</label>
                <input type="number" className="input" min={1} max={14} value={form.sessions_per_week}
                  onChange={e => setForm(f => ({ ...f, sessions_per_week: Number(e.target.value) }))} />
              </div>
            </div>

            <div>
              <label className="label">Kilometraje total del macrociclo</label>
              <div className="relative">
                <input type="number" className="input pr-12" min={10} value={form.total_km}
                  onChange={e => setForm(f => ({ ...f, total_km: Number(e.target.value) }))} />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">km</span>
              </div>
            </div>

            <div>
              <label className="label">Curva de progresión</label>
              <div className="space-y-2">
                {CURVES.map(c => (
                  <label key={c.value}
                    className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${form.progression_curve === c.value ? 'border-sky-500 bg-sky-500/10' : 'border-white/10 hover:border-white/20'}`}>
                    <input type="radio" name="curve" value={c.value} checked={form.progression_curve === c.value}
                      onChange={() => setForm(f => ({ ...f, progression_curve: c.value }))}
                      className="mt-0.5" />
                    <div>
                      <p className="text-white text-sm font-medium">{c.label}</p>
                      <p className="text-gray-400 text-xs">{c.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <button
              className="btn-primary w-full"
              onClick={() => setStep(2)}
              disabled={!form.name || !form.start_date}
            >
              Siguiente →
            </button>
          </div>
        )}

        {/* Step 2: Confirmación */}
        {step === 2 && (
          <div className="space-y-4">
            <h3 className="text-white font-semibold">Resumen</h3>
            <div className="bg-slate-800 rounded-xl p-4 space-y-2 text-sm">
              <Row label="Nombre" value={form.name} />
              <Row label="Inicio" value={form.start_date} />
              <Row label="Fin" value={calcEndDate(form.start_date, form.total_weeks)} />
              <Row label="Duración" value={`${form.total_weeks} semanas (${form.total_weeks / form.microcycle_weeks} microciclos de ${form.microcycle_weeks})`} />
              <Row label="Sesiones/semana" value={String(form.sessions_per_week)} />
              <Row label="Km totales" value={`${form.total_km} km`} />
              <Row label="Curva" value={CURVES.find(c => c.value === form.progression_curve)?.label ?? form.progression_curve} />
            </div>
            <p className="text-gray-400 text-sm">
              Las fases del macrociclo se crean automáticamente. Puedes editarlas después.
            </p>
            <div className="flex gap-3">
              <button className="btn-secondary flex-1" onClick={() => setStep(1)}>← Atrás</button>
              <button className="btn-primary flex-1" onClick={handleSubmit} disabled={createMacrocycle.isPending}>
                {createMacrocycle.isPending ? 'Creando...' : 'Crear macrociclo'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-400">{label}</span>
      <span className="text-white font-medium">{value}</span>
    </div>
  )
}
