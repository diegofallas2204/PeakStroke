// Asistente de creación de macrociclo en 3 pasos:
// 1) configuración general · 2) fases y competencias · 3) resumen.
import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Check, Plus, Trash2 } from 'lucide-react'
import { api } from '../../lib/api'
import { CURVES, PHASE_COLORS, POOLS } from '../../lib/constants'
import { Field, Modal } from '../../components/ui/primitives'

interface PhaseDraft { name: string; type: string; week_start: number; week_end: number; color: string }
interface CompDraft { name: string; week_number: number; days: number; is_main: boolean }

function defaultPhases(weeks: number): PhaseDraft[] {
  const base = Math.max(1, Math.round(weeks * 0.3))
  const build = Math.max(1, Math.round(weeks * 0.4))
  const peak = Math.max(1, Math.round(weeks * 0.2))
  const taper = Math.max(1, weeks - base - build - peak)
  let s = 1
  const mk = (name: string, type: string, len: number): PhaseDraft => {
    const phase = { name, type, week_start: s, week_end: s + len - 1, color: PHASE_COLORS[type] }
    s += len
    return phase
  }
  return [mk('Base', 'base', base), mk('Construcción', 'build', build), mk('Pico', 'peak', peak), mk('Descenso', 'taper', taper)]
}

const STEPS = ['Configuración', 'Fases y competencias', 'Resumen']

export function PlanWizard({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const [form, setForm] = useState({
    name: '', start_date: '', total_weeks: 12, weeks_per_micro: 4,
    total_km: 320, progression_curve: 'sigmoid', pool: '50', n_mac: 1, main_event: '', notes: '',
  })
  const [phases, setPhases] = useState<PhaseDraft[]>(defaultPhases(12))
  const [comps, setComps] = useState<CompDraft[]>([])
  const queryClient = useQueryClient()

  // Ajustes de estado durante el render (patrón oficial de React) en vez de efectos:
  // al abrir el asistente se vuelve al primer paso; al cambiar el total de semanas
  // se regeneran las fases por defecto.
  const [prevOpen, setPrevOpen] = useState(open)
  if (open !== prevOpen) {
    setPrevOpen(open)
    if (open) { setStep(0); setError('') }
  }
  const [prevWeeks, setPrevWeeks] = useState(form.total_weeks)
  if (form.total_weeks !== prevWeeks) {
    setPrevWeeks(form.total_weeks)
    setPhases(defaultPhases(form.total_weeks))
  }

  const mutation = useMutation({
    mutationFn: () => api.plans.create({
      ...form,
      main_event: form.main_event || null,
      notes: form.notes || null,
      phases,
      competitions: comps,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      onClose()
    },
    onError: (e: Error) => setError(e.message),
  })

  const phasesValid = useMemo(
    () => phases.every((p) => p.week_start >= 1 && p.week_end <= form.total_weeks && p.week_start <= p.week_end && p.name.trim()),
    [phases, form.total_weeks],
  )

  const next = () => {
    setError('')
    if (step === 0) {
      if (form.name.trim().length < 2) { setError('Ponle un nombre al macrociclo.'); return }
      if (!form.start_date) { setError('Selecciona la fecha de inicio.'); return }
    }
    if (step === 1 && !phasesValid) { setError('Revisa los rangos de semanas de las fases.'); return }
    setStep((s) => Math.min(s + 1, 2))
  }

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: ['total_weeks', 'weeks_per_micro', 'total_km', 'n_mac'].includes(key) ? Number(e.target.value) : e.target.value }))

  return (
    <Modal open={open} onClose={onClose} title="Nuevo macrociclo" wide>
      {/* Indicador de pasos */}
      <div className="mb-6 flex items-center gap-2">
        {STEPS.map((label, i) => (
          <div key={label} className="flex flex-1 items-center gap-2">
            <span
              className={`flex size-6 shrink-0 items-center justify-center rounded-full text-[10.5px] font-bold transition-all duration-300 ${
                i < step ? 'bg-mint text-ink' : i === step ? 'bg-accent text-white' : 'bg-surface-3 text-text-faint'
              }`}
            >
              {i < step ? <Check size={12} /> : i + 1}
            </span>
            <span className={`text-[11px] font-semibold ${i === step ? 'text-text' : 'text-text-faint'}`}>{label}</span>
            {i < STEPS.length - 1 && <div className="h-px flex-1 bg-line" />}
          </div>
        ))}
      </div>

      {step === 0 && (
        <div className="grid grid-cols-3 gap-4">
          <Field label="Nombre del macrociclo" className="col-span-3">
            <input className="field" value={form.name} onChange={set('name')} placeholder="Ej. Temporada Nacional 2026" autoFocus />
          </Field>
          <Field label="Fecha de inicio">
            <input type="date" className="field" value={form.start_date} onChange={set('start_date')} />
          </Field>
          <Field label="Duración (semanas)">
            <select className="field" value={form.total_weeks} onChange={set('total_weeks')}>
              {[12, 13, 14, 15, 16, 17, 18].map((w) => <option key={w} value={w}>{w} semanas</option>)}
            </select>
          </Field>
          <Field label="Semanas por microciclo">
            <select className="field" value={form.weeks_per_micro} onChange={set('weeks_per_micro')}>
              <option value={4}>4 semanas (3:1)</option>
              <option value={5}>5 semanas (4:1)</option>
            </select>
          </Field>
          <Field label="Kilometraje total (km)">
            <input type="number" className="field" value={form.total_km} onChange={set('total_km')} min={50} max={1500} />
          </Field>
          <Field label="Curva de progresión">
            <select className="field" value={form.progression_curve} onChange={set('progression_curve')}>
              {CURVES.map((c) => <option key={c.value} value={c.value}>{c.label}{c.value === 'sigmoid' ? ' (recomendada)' : ''}</option>)}
            </select>
          </Field>
          <Field label="Piscina">
            <select className="field" value={form.pool} onChange={set('pool')}>
              {POOLS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </Field>
          <Field label="Número de macrociclo">
            <select className="field" value={form.n_mac} onChange={set('n_mac')}>
              {[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}.° macrociclo</option>)}
            </select>
          </Field>
          <Field label="Evento objetivo">
            <input className="field" value={form.main_event} onChange={set('main_event')} placeholder="Ej. Nacional Juvenil" />
          </Field>
          <Field label="Objetivo / notas" className="col-span-3">
            <textarea className="field min-h-16 resize-y" value={form.notes} onChange={set('notes')} placeholder="Enfoque de la temporada, prioridades técnicas…" />
          </Field>
        </div>
      )}

      {step === 1 && (
        <div className="flex flex-col gap-5">
          <div>
            <div className="mb-2.5 flex items-center justify-between">
              <span className="card-title">Fases ({form.total_weeks} semanas)</span>
              <button
                className="btn btn-ghost !px-2.5 !py-1.5 text-[11px]"
                onClick={() => setPhases((p) => [...p, { name: 'Nueva fase', type: 'build', week_start: 1, week_end: 1, color: '#3b82f6' }])}
              >
                <Plus size={12} /> Fase
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {phases.map((phase, i) => (
                <div key={i} className="grid grid-cols-[18px_1fr_110px_90px_90px_34px] items-center gap-2.5 rounded-xl border border-line bg-surface-2 px-3 py-2">
                  <input
                    type="color" value={phase.color}
                    onChange={(e) => setPhases((p) => p.map((x, j) => j === i ? { ...x, color: e.target.value } : x))}
                    className="size-[18px] cursor-pointer rounded-full border-none bg-transparent"
                    aria-label="Color de fase"
                  />
                  <input className="field !py-1.5" value={phase.name}
                    onChange={(e) => setPhases((p) => p.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
                  <select className="field !py-1.5" value={phase.type}
                    onChange={(e) => setPhases((p) => p.map((x, j) => j === i ? { ...x, type: e.target.value, color: PHASE_COLORS[e.target.value] ?? x.color } : x))}>
                    <option value="base">Base</option><option value="build">Construcción</option>
                    <option value="peak">Pico</option><option value="taper">Descenso</option>
                  </select>
                  <input type="number" className="field !py-1.5 text-center" value={phase.week_start} min={1} max={form.total_weeks}
                    onChange={(e) => setPhases((p) => p.map((x, j) => j === i ? { ...x, week_start: Number(e.target.value) } : x))} />
                  <input type="number" className="field !py-1.5 text-center" value={phase.week_end} min={1} max={form.total_weeks}
                    onChange={(e) => setPhases((p) => p.map((x, j) => j === i ? { ...x, week_end: Number(e.target.value) } : x))} />
                  <button className="btn btn-danger !p-1.5" onClick={() => setPhases((p) => p.filter((_, j) => j !== i))} aria-label="Quitar fase">
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2.5 flex items-center justify-between">
              <span className="card-title">Competencias durante el ciclo</span>
              <button
                className="btn btn-ghost !px-2.5 !py-1.5 text-[11px]"
                onClick={() => setComps((c) => [...c, { name: '', week_number: form.total_weeks, days: 2, is_main: c.length === 0 }])}
              >
                <Plus size={12} /> Competencia
              </button>
            </div>
            {comps.length === 0 && (
              <p className="text-[11.5px] text-text-faint">Agrega las fechas de competencia para marcarlas en el plan (la principal suele ir al final).</p>
            )}
            <div className="flex flex-col gap-2">
              {comps.map((comp, i) => (
                <div key={i} className="grid grid-cols-[1fr_120px_100px_110px_34px] items-center gap-2.5 rounded-xl border border-line bg-surface-2 px-3 py-2">
                  <input className="field !py-1.5" placeholder="Nombre de la competencia" value={comp.name}
                    onChange={(e) => setComps((c) => c.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
                  <input type="number" className="field !py-1.5 text-center" value={comp.week_number} min={1} max={form.total_weeks}
                    onChange={(e) => setComps((c) => c.map((x, j) => j === i ? { ...x, week_number: Number(e.target.value) } : x))} />
                  <input type="number" className="field !py-1.5 text-center" value={comp.days} min={1} max={7}
                    onChange={(e) => setComps((c) => c.map((x, j) => j === i ? { ...x, days: Number(e.target.value) } : x))} />
                  <label className="flex items-center gap-1.5 text-[11px] text-text-dim">
                    <input type="checkbox" checked={comp.is_main}
                      onChange={(e) => setComps((c) => c.map((x, j) => j === i ? { ...x, is_main: e.target.checked } : x))} />
                    Principal
                  </label>
                  <button className="btn btn-danger !p-1.5" onClick={() => setComps((c) => c.filter((_, j) => j !== i))} aria-label="Quitar competencia">
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-3 gap-3">
            {[
              ['Nombre', form.name],
              ['Inicio', form.start_date],
              ['Duración', `${form.total_weeks} semanas · micros de ${form.weeks_per_micro}`],
              ['Kilometraje', `${form.total_km} km`],
              ['Curva', CURVES.find((c) => c.value === form.progression_curve)?.label ?? ''],
              ['Piscina', POOLS.find((p) => p.value === form.pool)?.label ?? ''],
              ['Macrociclo', `${form.n_mac}.°`],
              ['Evento', form.main_event || '—'],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl border border-line bg-surface-2 px-3.5 py-2.5">
                <p className="card-title !text-[9px]">{k}</p>
                <p className="mt-1 text-[12.5px] font-semibold">{v}</p>
              </div>
            ))}
          </div>
          <div className="flex h-9 gap-[3px]">
            {phases.map((phase, i) => (
              <div key={i} className="flex items-center justify-center rounded-lg text-[9.5px] font-bold uppercase tracking-wide"
                style={{ flex: phase.week_end - phase.week_start + 1, color: phase.color, background: `${phase.color}18`, border: `1px solid ${phase.color}30` }}>
                {phase.name}
              </div>
            ))}
          </div>
          <p className="text-[11.5px] text-text-dim">
            Al crear el macrociclo podrás <span className="font-semibold text-text">agregar atletas con sus pruebas</span>:
            el motor generará el plan semana a semana de cada uno y validará qué tan realista es su objetivo.
          </p>
        </div>
      )}

      {error && <p className="mt-4 text-xs text-coral">{error}</p>}

      <footer className="mt-6 flex justify-between">
        <button className="btn btn-ghost" onClick={() => step === 0 ? onClose() : setStep((s) => s - 1)}>
          <ArrowLeft size={13} /> {step === 0 ? 'Cancelar' : 'Atrás'}
        </button>
        {step < 2 ? (
          <button className="btn btn-primary" onClick={next}>Continuar <ArrowRight size={13} /></button>
        ) : (
          <button className="btn btn-primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            <Check size={13} /> Crear macrociclo
          </button>
        )}
      </footer>
    </Modal>
  )
}
