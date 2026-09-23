// Registro de test aeróbico con 4 modos de ingreso y análisis en vivo.
//
// **El intervalo de salida.** Un test se nada sobre un intervalo y el entrenador
// lee en el reloj la LLEGADA de cada repetición, no el tiempo nadado. Hasta el
// 2026-08-10 este formulario solo aceptaba tiempos nadados sin decirlo, así que
// quien apuntaba lo que el reloj marcaba —lo normal— guardaba una base aeróbica
// acumulada y disparatada. De ahí las dos cosas nuevas de aquí: el campo de
// salida y el conmutador de cómo hay que leer los números.
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../lib/api'
import type { InputMode } from '../../lib/types'
import { tryToSeconds, toClock } from '../../lib/format'
import { Field, Modal } from '../../components/ui/primitives'

const MODES = [
  { value: 'T30', label: 'T-30', hint: '30 repeticiones de 100m' },
  { value: 'T15', label: 'T-15', hint: '15 repeticiones de 100m' },
  { value: 'CUSTOM', label: 'Personalizado', hint: 'N repeticiones de cualquier distancia (ej. 12×400)' },
  { value: 'CSS', label: 'CSS 400/50', hint: 'Fórmula de Wakayoshi: 350/(T400−T50)' },
  { value: 'DIRECT', label: 'Directo', hint: 'Ya tienes el parcial calculado' },
]

export function TestForm({
  open, swimmerId, onClose,
}: { open: boolean; swimmerId: number | null; onClose: () => void }) {
  const [mode, setMode] = useState('T30')
  const [date, setDate] = useState('')
  const [splitsText, setSplitsText] = useState('')
  const [repDistance, setRepDistance] = useState(400)
  const [sendOffText, setSendOffText] = useState('')
  const [inputMode, setInputMode] = useState<InputMode>('rep')
  const [direct, setDirect] = useState('')
  const [t400, setT400] = useState('')
  const [t50, setT50] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const queryClient = useQueryClient()

  // Al abrir el formulario se limpian los campos y se fija la fecha de hoy.
  // Ajuste de estado durante el render (patrón oficial de React) en vez de efecto.
  const [prevOpen, setPrevOpen] = useState(open)
  if (open !== prevOpen) {
    setPrevOpen(open)
    if (open) {
      setError(''); setSplitsText(''); setDirect(''); setT400(''); setT50(''); setNotes('')
      setSendOffText(''); setInputMode('rep')
      setDate(new Date().toISOString().slice(0, 10))
    }
  }

  const splits = useMemo(
    () => splitsText.split(/[\n,;]+/).map((s) => s.trim()).filter(Boolean)
      .map(tryToSeconds).filter((v): v is number => v != null),
    [splitsText],
  )
  const expectedReps = mode === 'T30' ? 30 : mode === 'T15' ? 15 : null
  const effectiveRepDist = mode === 'CUSTOM' ? repDistance : 100
  const sendOff = tryToSeconds(sendOffText)
  // Sin salida no hay forma de despejar el tiempo nadado de una llegada, así que
  // el modo de reloj no se manda a medio configurar: se cae a `rep` hasta que la
  // haya. Es lo mismo que hace el backend, dicho antes de la petición.
  const effectiveInputMode: InputMode = sendOff == null ? 'rep' : inputMode

  // Análisis en vivo con debounce contra el motor.
  const { data: preview } = useQuery({
    queryKey: ['analyze', splits.join(','), effectiveRepDist, sendOff, effectiveInputMode],
    queryFn: () => api.aerobic.analyze(splits, effectiveRepDist, sendOff, effectiveInputMode),
    enabled: ['T30', 'T15', 'CUSTOM'].includes(mode) && splits.length >= 2,
    staleTime: Infinity,
    // Unas llegadas a medio teclear son incoherentes casi siempre y el backend
    // responde 422: reintentarlas solo multiplica peticiones que ya se sabe que
    // van a fallar.
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: () => api.aerobic.create({
      swimmer_id: swimmerId,
      test_type: mode,
      test_date: date,
      splits: ['T30', 'T15', 'CUSTOM'].includes(mode) ? splits : [],
      rep_distance: effectiveRepDist,
      send_off: sendOff,
      input_mode: effectiveInputMode,
      direct_per100: mode === 'DIRECT' ? tryToSeconds(direct) : null,
      t400: mode === 'CSS' ? tryToSeconds(t400) : null,
      t50: mode === 'CSS' ? tryToSeconds(t50) : null,
      notes: notes || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['aerobic'] })
      onClose()
    },
    onError: (e: Error) => setError(e.message),
  })

  const submit = () => {
    setError('')
    if (swimmerId == null) { setError('Selecciona un atleta primero.'); return }
    if (['T30', 'T15', 'CUSTOM'].includes(mode)) {
      if (splits.length < 2) { setError('Ingresa al menos 2 parciales válidos.'); return }
      if (expectedReps && splits.length !== expectedReps) {
        setError(`El ${mode === 'T30' ? 'T-30' : 'T-15'} requiere exactamente ${expectedReps} parciales (llevas ${splits.length}).`)
        return
      }
    }
    if (['T30', 'T15', 'CUSTOM'].includes(mode) && inputMode === 'clock' && sendOff == null) {
      setError('Para ingresar llegadas de reloj hace falta el intervalo de salida.')
      return
    }
    if (mode === 'DIRECT' && tryToSeconds(direct) == null) { setError('Ingresa el parcial aeróbico.'); return }
    if (mode === 'CSS' && (tryToSeconds(t400) == null || tryToSeconds(t50) == null)) {
      setError('Ingresa los tiempos de 400m y 50m.'); return
    }
    mutation.mutate()
  }

  return (
    <Modal open={open} onClose={onClose} title="Registrar test aeróbico" wide>
      <div className="mb-5 flex gap-2">
        {MODES.map((m) => (
          <button
            key={m.value}
            className={`btn flex-1 flex-col !items-start !gap-0.5 !py-2.5 ${mode === m.value ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setMode(m.value)}
          >
            <span className="text-[12px]">{m.label}</span>
            <span className={`text-[9px] font-normal leading-tight ${mode === m.value ? 'text-white/70' : 'text-text-faint'}`}>
              {m.hint}
            </span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Fecha del test">
          <input type="date" className="field" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>

        {mode === 'CUSTOM' && (
          <Field label="Distancia por repetición (m)">
            <input type="number" className="field" value={repDistance} min={25} max={2000} step={25}
              onChange={(e) => setRepDistance(Number(e.target.value))} />
          </Field>
        )}
        {mode === 'DIRECT' && (
          <Field label="Parcial aeróbico (por 100m)">
            <input className="field mono" placeholder="1:18.50" value={direct} onChange={(e) => setDirect(e.target.value)} />
          </Field>
        )}
        {mode === 'CSS' && (
          <>
            <Field label="Tiempo 400m">
              <input className="field mono" placeholder="4:52.00" value={t400} onChange={(e) => setT400(e.target.value)} />
            </Field>
            <Field label="Tiempo 50m">
              <input className="field mono" placeholder="27.90" value={t50} onChange={(e) => setT50(e.target.value)} />
            </Field>
          </>
        )}

        {['T30', 'T15', 'CUSTOM'].includes(mode) && (
          <>
            <Field label="Salida (intervalo)">
              <input
                className="field mono"
                placeholder="1:30 — opcional"
                value={sendOffText}
                onChange={(e) => setSendOffText(e.target.value)}
              />
              <p className="mt-1.5 text-[10.5px] leading-relaxed text-text-faint">
                Cada cuánto sale la repetición. Es lo que falta para prescribir
                los tiempos de entrenamiento: el ritmo dice a qué nadar, la
                salida cada cuánto.
              </p>
            </Field>

            <Field label="Qué estás apuntando">
              <div className="flex gap-2">
                {([
                  ['rep', 'Tiempo de nado', 'Lo que tardó cada repetición'],
                  ['clock', 'Llegada en el reloj', 'El reloj sigue corriendo entre salidas'],
                ] as const).map(([value, label, hint]) => (
                  <button
                    key={value}
                    type="button"
                    disabled={value === 'clock' && sendOff == null}
                    className={`btn flex-1 flex-col !items-start !gap-0.5 !py-2 ${
                      effectiveInputMode === value ? 'btn-primary' : 'btn-ghost'
                    } disabled:opacity-40`}
                    onClick={() => setInputMode(value)}
                  >
                    <span className="text-[11px]">{label}</span>
                    <span className={`text-[9px] font-normal leading-tight ${
                      effectiveInputMode === value ? 'text-white/70' : 'text-text-faint'
                    }`}>
                      {hint}
                    </span>
                  </button>
                ))}
              </div>
              {sendOff == null && (
                <p className="mt-1.5 text-[10.5px] text-text-faint">
                  Las llegadas necesitan la salida para despejar el tiempo nadado.
                </p>
              )}
            </Field>

            <Field
              label={`Parciales (${splits.length}${expectedReps ? `/${expectedReps}` : ''}) — separados por coma o salto de línea`}
              className="col-span-2"
            >
              <textarea
                className="field mono min-h-28 resize-y"
                placeholder={
                  effectiveInputMode === 'clock'
                    ? '1:18.2, 2:49.0, 4:20.1, … (acumuladas)'
                    : mode === 'CUSTOM' ? '5:02.0, 5:04.5, 5:01.2, …' : '1:18.2, 1:18.9, 1:17.8, …'
                }
                value={splitsText}
                onChange={(e) => setSplitsText(e.target.value)}
              />
            </Field>
          </>
        )}

        <Field label="Notas" className="col-span-2">
          <input className="field" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Condiciones del test, sensaciones…" />
        </Field>
      </div>

      {preview && (
        <div className="mt-4 rounded-xl border border-line bg-surface-2 p-3.5">
          <div className={`grid gap-3 ${preview.avg_rest != null ? 'grid-cols-5' : 'grid-cols-3'}`}>
            <div>
              <p className="card-title !text-[9px]">Base aeróbica</p>
              <p className="mono mt-0.5 text-lg font-bold text-accent-soft">{toClock(preview.avg_per100)} <span className="text-[10px] text-text-faint">/100m</span></p>
            </div>
            <div>
              <p className="card-title !text-[9px]">Consistencia</p>
              <p className="mono mt-0.5 text-lg font-bold text-cyan">±{preview.std_dev.toFixed(2)}s</p>
            </div>
            <div>
              <p className="card-title !text-[9px]">Tendencia</p>
              <p className="mt-0.5 text-lg font-bold" style={{ color: preview.trend === 'improving' ? '#34d399' : preview.trend === 'declining' ? '#fb7185' : '#22d3ee' }}>
                {preview.trend === 'improving' ? 'En mejora' : preview.trend === 'declining' ? 'Se cae' : 'Estable'}
              </p>
            </div>
            {preview.avg_rest != null && (
              <>
                <div>
                  <p className="card-title !text-[9px]">Descanso medio</p>
                  <p className="mono mt-0.5 text-lg font-bold text-mint">{preview.avg_rest.toFixed(1)}s</p>
                </div>
                <div>
                  <p className="card-title !text-[9px]">Densidad</p>
                  <p className="mono mt-0.5 text-lg font-bold text-amber">
                    {preview.density != null ? `${(preview.density * 100).toFixed(0)}%` : '—'}
                  </p>
                </div>
              </>
            )}
          </div>

          {/* No aguantar el intervalo es un dato del test, no un error de
              captura: se enseña y se guarda igual. */}
          {preview.missed_intervals.length > 0 && (
            <p className="mt-3 border-t border-line pt-2.5 text-[11px] leading-relaxed text-amber">
              No llegó antes de la salida en {preview.missed_intervals.length}{' '}
              {preview.missed_intervals.length === 1 ? 'repetición' : 'repeticiones'}
              {' '}(nº {preview.missed_intervals.join(', ')}). El test se guarda igual:
              es información sobre el intervalo, no un error de captura.
            </p>
          )}
        </div>
      )}

      {error && <p className="mt-3 text-xs text-coral">{error}</p>}

      <footer className="mt-5 flex justify-end gap-2.5">
        <button className="btn btn-ghost" onClick={onClose}>Cancelar</button>
        <button className="btn btn-primary" onClick={submit} disabled={mutation.isPending}>
          Guardar test
        </button>
      </footer>
    </Modal>
  )
}
