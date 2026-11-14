// Apuntar un test de lactato al borde de la piscina.
//
// Una fila por repetición y solo el tiempo obligatorio: lactato, FC, esfuerzo y
// brazadas se apuntan cuando se miden. En el celular cada fila ocupa dos líneas
// (tiempo, lactato, FC · esfuerzo, brazadas). Lo que se teclea se lee con
// `lib/lactato.ts`, que entiende «-», «NA», «6-7» o «31/31/30/30»; lo que no
// entiende marca el campo en rojo en vez de guardarse como otra cosa.
//
// Mientras se escribe, `/analyze` devuelve los avisos de calidad. Avisan, no
// bloquean: el test se guarda igual.
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Save } from 'lucide-react'
import { api } from '../../lib/api'
import type { LactateTestCreate, ZonaDeLactato } from '../../lib/types'
import { ZONE_ORDER } from '../../lib/constants'
import { isoDay, toClock, tryToSeconds } from '../../lib/format'
import { parsearBrazadas, parsearEsfuerzo, parsearNumero } from '../../lib/lactato'
import { Field, Modal, Segmented, Toggle } from '../../components/ui/primitives'

type Fila = { tiempo: string; lactato: string; fc: string; esfuerzo: string; brazadas: string; tramo: string }
const VACIA: Fila = { tiempo: '', lactato: '', fc: '', esfuerzo: '', brazadas: '', tramo: '' }
const MAX_REPS = 40

const opcional = (t: string) => (t.trim() ? tryToSeconds(t) ?? undefined : null)

type Props = { open: boolean; swimmerId: number | null; onClose: () => void; onCreado: (id: number) => void }

// El modal solo monta su contenido abierto: cada apertura nace con el estado
// limpio, sin un efecto que lo reinicie.
export function LactatoForm(props: Props) {
  return (
    <Modal open={props.open} onClose={props.onClose} title="Test de lactato" wide>
      <Formulario {...props} />
    </Modal>
  )
}

function Formulario({ open, swimmerId, onClose, onCreado }: Props) {
  const [fecha, setFecha] = useState(() => isoDay(new Date()))
  const [zona, setZona] = useState<ZonaDeLactato>('R1')
  const [distancia, setDistancia] = useState('400')
  const [descansoTipo, setDescansoTipo] = useState<'pausa' | 'salida'>('pausa')
  const [descanso, setDescanso] = useState('30')
  const [propMin, setPropMin] = useState('')
  const [propMax, setPropMax] = useState('')
  const [referencia, setReferencia] = useState('')
  const [tramoM, setTramoM] = useState('50')
  const [conTramo, setConTramo] = useState(false)
  const [sitio, setSitio] = useState<'' | 'dedo' | 'lobulo'>('')
  const [analizador, setAnalizador] = useState('')
  const [minuto, setMinuto] = useState('')
  const [metodoFc, setMetodoFc] = useState<'' | 'banda' | 'palpacion' | 'optico'>('')
  const [notas, setNotas] = useState('')
  const [filas, setFilas] = useState<Fila[]>(() => Array.from({ length: 8 }, () => ({ ...VACIA })))

  const cambiarReps = (n: number) => {
    const total = Math.min(Math.max(n, 1), MAX_REPS)
    setFilas((f) => Array.from({ length: total }, (_, i) => f[i] ?? { ...VACIA }))
  }
  const editar = (i: number, campo: keyof Fila, valor: string) =>
    setFilas((f) => f.map((fila, j) => (j === i ? { ...fila, [campo]: valor } : fila)))

  // Lo que se manda, y qué celdas no se entienden.
  const { cuerpo, malas } = useMemo(() => {
    const malas = new Set<string>()
    const reps = filas.map((f, i) => {
      const tiempo = tryToSeconds(f.tiempo)
      const lactato = parsearNumero(f.lactato)
      const fc = parsearNumero(f.fc)
      const esfuerzo = parsearEsfuerzo(f.esfuerzo)
      const brazadas = parsearBrazadas(f.brazadas)
      const tramo = conTramo ? opcional(f.tramo) : null
      if (tiempo == null && f.tiempo.trim()) malas.add(`${i}.tiempo`)
      if (lactato === undefined) malas.add(`${i}.lactato`)
      if (fc === undefined || (fc != null && !Number.isInteger(fc))) malas.add(`${i}.fc`)
      if (esfuerzo === undefined) malas.add(`${i}.esfuerzo`)
      if (brazadas === undefined) malas.add(`${i}.brazadas`)
      if (tramo === undefined) malas.add(`${i}.tramo`)
      return {
        swim_time: tiempo ?? 0, lactate: lactato ?? null, heart_rate: fc ?? null,
        effort: esfuerzo ?? null, stroke_counts: brazadas ?? [], segment_time: tramo ?? null,
      }
    })
    const completo = swimmerId != null && fecha && reps.every((r) => r.swim_time > 0) && malas.size === 0
    const segundos = (t: string) => (t.trim() ? tryToSeconds(t) : null)
    const cuerpo: LactateTestCreate | null = completo ? {
      swimmer_id: swimmerId, test_date: fecha, target_zone: zona, rep_distance: Number(distancia) || 400,
      rest_type: descanso.trim() ? descansoTipo : null, rest_s: segundos(descanso),
      proposed_min: segundos(propMin), proposed_max: segundos(propMax), reference_time: segundos(referencia),
      counted_segment_m: Number(tramoM) || null,
      sample_site: sitio || null, analyzer: analizador.trim() || null,
      sample_minute: parsearNumero(minuto) ?? null, hr_method: metodoFc || null,
      notes: notas.trim() || null, reps,
    } : null
    return { cuerpo, malas }
  }, [filas, conTramo, swimmerId, fecha, zona, distancia, descanso, descansoTipo, propMin, propMax,
    referencia, tramoM, sitio, analizador, minuto, metodoFc, notas])

  // Análisis en vivo, medio segundo después de dejar de teclear.
  const [enEspera, setEnEspera] = useState<LactateTestCreate | null>(null)
  useEffect(() => {
    const t = setTimeout(() => setEnEspera(cuerpo), 500)
    return () => clearTimeout(t)
  }, [cuerpo])
  const { data: analisis, error: errorDeAnalisis } = useQuery({
    queryKey: ['lactate-analyze', JSON.stringify(enEspera)],
    queryFn: () => api.lactate.analyze(enEspera!),
    enabled: open && enEspera != null,
    retry: false,
  })
  const avisados = new Set(analisis?.warnings.map((w) => w.rep_number))

  const queryClient = useQueryClient()
  const guardar = useMutation({
    mutationFn: (datos: LactateTestCreate) => api.lactate.create(datos),
    onSuccess: (test) => {
      queryClient.invalidateQueries({ queryKey: ['lactate'] })
      onCreado(test.id)
      onClose()
    },
  })

  const celda = (i: number, campo: keyof Fila, etiqueta: string, extra = '') => (
    <input
      className={`field !px-2 !py-1.5 text-[12.5px] ${malas.has(`${i}.${campo}`) ? '!border-coral' : ''} ${extra}`}
      inputMode={campo === 'brazadas' ? 'text' : 'decimal'} placeholder={etiqueta}
      aria-label={`Repetición ${i + 1}: ${etiqueta}`} aria-invalid={malas.has(`${i}.${campo}`)}
      value={filas[i][campo]} onChange={(e) => editar(i, campo, e.target.value)}
    />
  )

  return (
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="Fecha"><input type="date" className="field" value={fecha} onChange={(e) => setFecha(e.target.value)} /></Field>
          <Field label="Zona buscada">
            <select className="field" value={zona} onChange={(e) => setZona(e.target.value as ZonaDeLactato)}>
              {ZONE_ORDER.map((z) => <option key={z} value={z}>{z}</option>)}
            </select>
          </Field>
          <Field label="Repeticiones × m">
            <div className="flex items-center gap-1.5">
              <input className="field !w-16" type="number" min={1} max={MAX_REPS} value={filas.length}
                onChange={(e) => cambiarReps(Number(e.target.value))} aria-label="Repeticiones" />
              <span className="text-text-faint">×</span>
              <input className="field" inputMode="numeric" value={distancia} onChange={(e) => setDistancia(e.target.value)} aria-label="Metros por repetición" />
            </div>
          </Field>
          <Field label="Descanso" className="col-span-2 sm:col-span-1">
            <div className="flex items-center gap-1.5">
              <Segmented label="Tipo de descanso" value={descansoTipo} onChange={setDescansoTipo}
                options={[{ value: 'pausa', label: 'Pausa' }, { value: 'salida', label: 'Salida' }]} />
              <input className="field" placeholder="0:30" value={descanso} onChange={(e) => setDescanso(e.target.value)} aria-label="Segundos de descanso" />
            </div>
          </Field>
          <Field label="Propuesto (de–a)">
            <div className="flex items-center gap-1.5">
              <input className="field" placeholder="5:04" value={propMin} onChange={(e) => setPropMin(e.target.value)} aria-label="Propuesto desde" />
              <input className="field" placeholder="5:06" value={propMax} onChange={(e) => setPropMax(e.target.value)} aria-label="Propuesto hasta" />
            </div>
          </Field>
          <Field label="Su mejor marca"><input className="field" placeholder="4:05.12" value={referencia} onChange={(e) => setReferencia(e.target.value)} /></Field>
          <Field label="Tramo contado (m)"><input className="field" inputMode="numeric" value={tramoM} onChange={(e) => setTramoM(e.target.value)} /></Field>
          <div className="self-end"><Toggle checked={conTramo} onChange={setConTramo} label="Tiempo del tramo" /></div>
        </div>

        <details className="rounded-xl border border-line px-3 py-2 text-[12px]">
          <summary className="cursor-pointer font-semibold text-text-dim">Cómo se midió</summary>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Field label="Muestra">
              <Segmented label="Sitio de la muestra" value={sitio} onChange={setSitio}
                options={[{ value: '', label: '—' }, { value: 'dedo', label: 'Dedo' }, { value: 'lobulo', label: 'Lóbulo' }]} />
            </Field>
            <Field label="Analizador"><input className="field" maxLength={60} value={analizador} onChange={(e) => setAnalizador(e.target.value)} /></Field>
            <Field label="Minuto tras la rep."><input className="field" inputMode="decimal" value={minuto} onChange={(e) => setMinuto(e.target.value)} /></Field>
            <Field label="FC">
              <select className="field" value={metodoFc} onChange={(e) => setMetodoFc(e.target.value as typeof metodoFc)}>
                <option value="">—</option><option value="banda">Banda</option>
                <option value="palpacion">Palpación</option><option value="optico">Óptico</option>
              </select>
            </Field>
          </div>
        </details>

        <div className="flex flex-col gap-1.5">
          <div className="hidden grid-cols-[1.75rem_5rem_4.5rem_4.5rem_4.5rem_1fr] gap-1.5 px-0.5 text-[10px] uppercase tracking-wider text-text-faint sm:grid" aria-hidden>
            <span>#</span><span>Tiempo</span><span>mmol/L</span><span>FC</span><span>CR-10</span><span>Brazadas{conTramo ? ' · tramo' : ''}</span>
          </div>
          {filas.map((_, i) => (
            <div key={i} className="grid grid-cols-[1.75rem_1fr_1fr_1fr] items-center gap-1.5 sm:grid-cols-[1.75rem_5rem_4.5rem_4.5rem_4.5rem_1fr]">
              <span className={`mono text-[11px] ${avisados.has(i + 1) ? 'font-bold text-amber' : 'text-text-faint'}`}>{i + 1}</span>
              {celda(i, 'tiempo', 'Tiempo')}
              {celda(i, 'lactato', 'mmol/L')}
              {celda(i, 'fc', 'FC')}
              {celda(i, 'esfuerzo', 'CR-10', 'col-start-2 sm:col-start-auto')}
              <div className={`col-span-2 flex gap-1.5 sm:col-span-1`}>
                {celda(i, 'brazadas', 'Brazadas', 'min-w-0 flex-1')}
                {conTramo && celda(i, 'tramo', 'Tramo', '!w-20')}
              </div>
            </div>
          ))}
        </div>

        {analisis && (
          <div className="rounded-xl bg-surface-2 px-3 py-2.5 text-[12px]">
            <p className="text-text-dim">
              Media <b className="mono text-text">{toClock(analisis.summary.mean_time, 1)}</b>
              {' · '}CV {analisis.summary.cv_pct.toFixed(1)} %
              {analisis.summary.lactate_median != null && <> · lactato {analisis.summary.lactate_median} mmol/L</>}
            </p>
            {analisis.warnings.map((w) => (
              <p key={`${w.rep_number}-${w.field}`} className="mt-1 flex gap-1.5 text-amber">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" /> #{w.rep_number} · {w.message}
              </p>
            ))}
          </div>
        )}
        {errorDeAnalisis && <p className="text-[12px] text-coral">{(errorDeAnalisis as Error).message}</p>}
        <Field label="Notas"><textarea className="field min-h-14" maxLength={2000} value={notas} onChange={(e) => setNotas(e.target.value)} /></Field>

        <button
          className="btn btn-primary justify-center" disabled={!cuerpo || guardar.isPending}
          onClick={() => cuerpo && guardar.mutate(cuerpo)}
        >
          <Save size={14} /> {guardar.isPending ? 'Guardando…' : 'Guardar test'}
        </button>
      </div>
  )
}
