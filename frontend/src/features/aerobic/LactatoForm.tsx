// Apuntar un test de lactato con la forma de la plantilla del entrenador
// (`Tabla Medición`): cabecera, una fila por repetición y el pie con el
// promedio, la intensidad y la recuperación.
//
// Solo el tiempo es obligatorio. Las columnas que no se usan se ocultan (y eso
// se recuerda); las de cálculo se rellenan solas mientras se escribe, con el
// mismo análisis que se guardará. Lo tecleado se lee con `lib/lactato.ts`, que
// entiende «-», «NA», «6-7» o «31/31/30/30»; lo que no entiende queda en rojo.
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Plus, Save, X } from 'lucide-react'
import { api } from '../../lib/api'
import type { LactateTestCreate, ZonaDeLactato } from '../../lib/types'
import { STROKE_LABEL, ZONE_ORDER } from '../../lib/constants'
import { isoDay, toClock, tryToSeconds } from '../../lib/format'
import { parsearBrazadas, parsearEsfuerzo, parsearNumero, parsearTiempos } from '../../lib/lactato'
import { Field, Modal, Segmented } from '../../components/ui/primitives'
import { Calculado, SelectorDeColumnas, TablaDeLactato } from './TablaDeLactato'
import { useColumnasDeLactato, type ClaveDeColumna } from './lactatoColumnas'

type Celdas = Record<'serie' | 'tiempo' | 'intensidad' | 'lactato' | 'fc' | 'brazadas' | 'parciales' | 'tramo', string>
const VACIA: Celdas = { serie: '', tiempo: '', intensidad: '', lactato: '', fc: '', brazadas: '', parciales: '', tramo: '' }
type Recup = { minuto: string; fc: string; lactato: string }
const MAX_REPS = 40
// Minutos habituales para ver el pico y cómo baja (el pico no llega al terminar).
const MINUTOS = [3, 5, 7, 10, 15, 20]

type Props = {
  open: boolean
  swimmerId: number | null
  atleta?: { name: string; age: number | null; main_stroke?: string } | null
  onClose: () => void
  onCreado: (id: number) => void
}

// El modal solo monta su contenido abierto: cada apertura nace limpia.
export function LactatoForm(props: Props) {
  return (
    <Modal open={props.open} onClose={props.onClose} title="Test de lactato" wide>
      <Formulario {...props} />
    </Modal>
  )
}

const seg = (t: string) => (t.trim() ? tryToSeconds(t) : null)
const par = (a: string, b: string): [number | null, number | null] => [seg(a), seg(b)]

function Formulario({ open, swimmerId, atleta, onClose, onCreado }: Props) {
  const vista = useColumnasDeLactato()
  const [fecha, setFecha] = useState(() => isoDay(new Date()))
  const [zona, setZona] = useState<ZonaDeLactato>('R1')
  const [distancia, setDistancia] = useState('400')
  const [estilo, setEstilo] = useState(atleta?.main_stroke && atleta.main_stroke in STROKE_LABEL ? atleta.main_stroke : 'libre')
  const [piscina, setPiscina] = useState<'25' | '50'>('50')
  const [propMin, setPropMin] = useState('')
  const [propMax, setPropMax] = useState('')
  const [intMin, setIntMin] = useState('')
  const [intMax, setIntMax] = useState('')
  const [descansoTipo, setDescansoTipo] = useState<'pausa' | 'salida'>('pausa')
  const [descanso, setDescanso] = useState('30')
  const [referencia, setReferencia] = useState('')
  const [tramoM, setTramoM] = useState('50')
  const [sitio, setSitio] = useState<'' | 'dedo' | 'lobulo'>('')
  const [analizador, setAnalizador] = useState('')
  const [minuto, setMinuto] = useState('')
  const [metodoFc, setMetodoFc] = useState<'' | 'banda' | 'palpacion' | 'optico'>('')
  const [notas, setNotas] = useState('')
  const [filas, setFilas] = useState<Celdas[]>(() => Array.from({ length: 8 }, () => ({ ...VACIA })))
  // «Tiempo Actual» sugerido: su marca en la inscripción para esa misma prueba
  // (distancia y estilo). Es lo que la plantilla llama así (TODO-37). La consulta
  // es la de Macrociclos, ya en caché casi siempre.
  const { data: planes } = useQuery({ queryKey: ['plans'], queryFn: api.plans.list })
  const marcas = (planes ?? []).flatMap((p) => p.athletes)
    .filter((a) => a.swimmer_id === swimmerId)
    .flatMap((a) => a.events)
    .filter((e) => e.distance === Number(distancia) && e.stroke === estilo)
    .map((e) => e.current_time)
  const marcaSugerida = marcas.length ? Math.min(...marcas) : null
  const [recup, setRecup] = useState<Recup[]>([])

  const cambiarReps = (n: number) => {
    const total = Math.min(Math.max(n, 1), MAX_REPS)
    setFilas((f) => Array.from({ length: total }, (_, i) => f[i] ?? { ...VACIA }))
  }
  const editar = (i: number, campo: keyof Celdas, valor: string) =>
    setFilas((f) => f.map((fila, j) => (j === i ? { ...fila, [campo]: valor } : fila)))
  const editarRecup = (i: number, campo: keyof Recup, valor: string) =>
    setRecup((r) => r.map((fila, j) => (j === i ? { ...fila, [campo]: valor } : fila)))
  const otroMinuto = () => setRecup((r) => {
    const ultimo = Number(r.at(-1)?.minuto) || 0
    const siguiente = MINUTOS.find((m) => m > ultimo) ?? ultimo + 5
    return [...r, { minuto: String(siguiente), fc: '', lactato: '' }]
  })

  // Cada fila leída, qué celdas no se entienden, y el cuerpo que se manda.
  const { reps, malas, completas, cabecera } = useMemo(() => {
    const malas = new Set<string>()
    const reps = filas.map((f, i) => {
      const r = {
        swim_time: tryToSeconds(f.tiempo) ?? 0,
        series: parsearNumero(f.serie), lactate: parsearNumero(f.lactato), heart_rate: parsearNumero(f.fc),
        effort: parsearEsfuerzo(f.intensidad), stroke_counts: parsearBrazadas(f.brazadas),
        splits: parsearTiempos(f.parciales), segment_time: f.tramo.trim() ? tryToSeconds(f.tramo) ?? undefined : null,
      }
      if (!r.swim_time && f.tiempo.trim()) malas.add(`${i}.tiempo`)
      if (r.series === undefined || (r.series != null && !(Number.isInteger(r.series) && r.series >= 1))) malas.add(`${i}.serie`)
      if (r.lactate === undefined) malas.add(`${i}.lactato`)
      if (r.heart_rate === undefined || (r.heart_rate != null && !Number.isInteger(r.heart_rate))) malas.add(`${i}.fc`)
      if (r.effort === undefined) malas.add(`${i}.intensidad`)
      if (r.stroke_counts === undefined) malas.add(`${i}.brazadas`)
      if (r.splits === undefined) malas.add(`${i}.parciales`)
      if (r.segment_time === undefined) malas.add(`${i}.tramo`)
      return {
        swim_time: r.swim_time, series: r.series ?? null, lactate: r.lactate ?? null, heart_rate: r.heart_rate ?? null,
        effort: r.effort ?? null, stroke_counts: r.stroke_counts ?? [], splits: r.splits ?? [], segment_time: r.segment_time ?? null,
      }
    })
    const completas = reps.map((r, i) => r.swim_time > 0 && ![...malas].some((k) => k.startsWith(`${i}.`)))
    const [pMin, pMax] = par(propMin, propMax)
    const iMin = parsearNumero(intMin) ?? null
    const iMax = parsearNumero(intMax) ?? null
    const cabecera: Omit<LactateTestCreate, 'reps'> | null = swimmerId == null || !fecha ? null : {
      swimmer_id: swimmerId, test_date: fecha, target_zone: zona, rep_distance: Number(distancia) || 400,
      stroke: estilo, pool_length: Number(piscina) as 25 | 50,
      proposed_min: pMin, proposed_max: pMax, proposed_intensity_min: iMin, proposed_intensity_max: iMax,
      rest_type: descanso.trim() ? descansoTipo : null, rest_s: seg(descanso), reference_time: seg(referencia),
      counted_segment_m: Number(tramoM) || null,
      sample_site: sitio || null, analyzer: analizador.trim() || null,
      sample_minute: parsearNumero(minuto) ?? null, hr_method: metodoFc || null, notes: notas.trim() || null,
      recovery: recup
        .map((m) => ({ minute: Number(m.minuto), heart_rate: parsearNumero(m.fc) ?? null, lactate: parsearNumero(m.lactato) ?? null }))
        .filter((m) => Number.isFinite(m.minute) && (m.heart_rate != null || m.lactate != null)),
    }
    return { reps, malas, completas, cabecera }
  }, [filas, recup, swimmerId, fecha, zona, distancia, estilo, piscina, propMin, propMax, intMin, intMax,
    descanso, descansoTipo, referencia, tramoM, sitio, analizador, minuto, metodoFc, notas])

  const cuerpo = cabecera && completas.every(Boolean) ? { ...cabecera, reps } : null
  // La vista previa analiza las filas que ya tienen tiempo: los cálculos salen
  // mientras se escribe, sin esperar a la última repetición.
  const incluidas = completas.flatMap((ok, i) => (ok ? [i] : []))
  const previa = cabecera && incluidas.length ? { ...cabecera, reps: incluidas.map((i) => reps[i]) } : null

  const [enEspera, setEnEspera] = useState<{ cuerpo: LactateTestCreate; indices: number[] } | null>(null)
  const clave = JSON.stringify(previa)
  useEffect(() => {
    const t = setTimeout(() => setEnEspera(previa ? { cuerpo: previa, indices: incluidas } : null), 450)
    return () => clearTimeout(t)
    // `clave` resume `previa` e `incluidas`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave])
  const { data: analisis, error: errorDeAnalisis } = useQuery({
    queryKey: ['lactate-analyze', JSON.stringify(enEspera)],
    queryFn: () => api.lactate.analyze(enEspera!.cuerpo),
    enabled: open && enEspera != null,
    retry: false,
  })
  const calculada = (i: number) => {
    const k = enEspera?.indices.indexOf(i) ?? -1
    return k >= 0 ? analisis?.reps[k] : undefined
  }
  const filaDeRep = (n: number) => enEspera?.indices[n - 1] ?? n - 1
  const avisadas = new Set(analisis?.warnings.map((w) => filaDeRep(w.rep_number)))

  const queryClient = useQueryClient()
  const guardar = useMutation({
    mutationFn: (datos: LactateTestCreate) => api.lactate.create(datos),
    onSuccess: (test) => {
      queryClient.invalidateQueries({ queryKey: ['lactate'] })
      onCreado(test.id)
      onClose()
    },
  })

  const campo = (i: number, clave: keyof Celdas, ancho: string) => (
    <input
      className={`field !px-2 !py-1 text-[12.5px] ${ancho} ${malas.has(`${i}.${clave}`) ? '!border-coral' : ''}`}
      inputMode={clave === 'brazadas' || clave === 'parciales' ? 'text' : 'decimal'}
      aria-label={`Repetición ${i + 1}: ${clave}`} aria-invalid={malas.has(`${i}.${clave}`)}
      value={filas[i][clave]} onChange={(e) => editar(i, clave, e.target.value)}
    />
  )
  const celda = (clave: ClaveDeColumna, i: number) => {
    const c = calculada(i)
    switch (clave) {
      case 'velocidad': return <Calculado valor={c?.speed} />
      case 'frecuencia': return <Calculado valor={c?.cycle_rate} decimales={1} />
      case 'efectividad': return <Calculado valor={c?.m_per_cycle} />
      case 'metros': return <Calculado valor={c?.m_per_stroke} />
      case 'serie': return campo(i, 'serie', '!w-12')
      case 'tiempo': return campo(i, 'tiempo', '!w-20')
      case 'intensidad': return campo(i, 'intensidad', '!w-14')
      case 'lactato': return campo(i, 'lactato', '!w-16')
      case 'fc': return campo(i, 'fc', '!w-16')
      case 'brazadas': return campo(i, 'brazadas', '!w-36')
      case 'parciales': return campo(i, 'parciales', '!w-44')
      case 'tramo': return campo(i, 'tramo', '!w-20')
    }
  }
  const s = analisis?.summary

  return (
    <div className="flex flex-col gap-4">
      {/* Cabecera de la plantilla, en su orden. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Nombre"><p className="field truncate !bg-transparent">{atleta?.name ?? '—'}</p></Field>
        <Field label="Edad"><p className="field !bg-transparent">{atleta?.age != null ? `${atleta.age} años` : '—'}</p></Field>
        <Field label="Fecha"><input type="date" className="field" value={fecha} onChange={(e) => setFecha(e.target.value)} /></Field>
        <Field label="Capacidad">
          <select className="field" value={zona} onChange={(e) => setZona(e.target.value as ZonaDeLactato)}>
            {ZONE_ORDER.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </Field>
        <Field label="Prueba">
          <div className="flex items-center gap-1.5">
            <input className="field !w-14" type="number" min={1} max={MAX_REPS} value={filas.length}
              onChange={(e) => cambiarReps(Number(e.target.value))} aria-label="Repeticiones" />
            <span className="text-text-faint">×</span>
            <input className="field" inputMode="numeric" value={distancia} onChange={(e) => setDistancia(e.target.value)} aria-label="Metros por repetición" />
          </div>
        </Field>
        <Field label="Técnica">
          <select className="field" value={estilo} onChange={(e) => setEstilo(e.target.value)}>
            {Object.entries(STROKE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
        <Field label="Piscina">
          <Segmented label="Piscina" value={piscina} onChange={setPiscina}
            options={[{ value: '25', label: '25 m' }, { value: '50', label: '50 m' }]} />
        </Field>
        <Field label="Pausas">
          <div className="flex items-center gap-1.5">
            <Segmented label="Tipo de descanso" value={descansoTipo} onChange={setDescansoTipo}
              options={[{ value: 'pausa', label: 'Pausa' }, { value: 'salida', label: 'Salida' }]} />
            <input className="field min-w-0" placeholder="30" value={descanso} onChange={(e) => setDescanso(e.target.value)} aria-label="Segundos de descanso" />
          </div>
        </Field>
        <Field label="Tiempo Pro">
          <div className="flex items-center gap-1">
            <input className="field min-w-0" placeholder="5:04" value={propMin} onChange={(e) => setPropMin(e.target.value)} aria-label="Tiempo propuesto desde" />
            <span className="text-text-faint">/</span>
            <input className="field min-w-0" placeholder="5:06" value={propMax} onChange={(e) => setPropMax(e.target.value)} aria-label="Tiempo propuesto hasta" />
          </div>
        </Field>
        <Field label="Intens. Pro (%)">
          <div className="flex items-center gap-1">
            <input className="field min-w-0" inputMode="decimal" placeholder="75" value={intMin} onChange={(e) => setIntMin(e.target.value)} aria-label="Intensidad propuesta desde" />
            <span className="text-text-faint">–</span>
            <input className="field min-w-0" inputMode="decimal" placeholder="80" value={intMax} onChange={(e) => setIntMax(e.target.value)} aria-label="Intensidad propuesta hasta" />
          </div>
        </Field>
        <Field label="Tiempo Actual">
          <input className="field" placeholder={marcaSugerida ? toClock(marcaSugerida) : '4:05.12'} value={referencia} onChange={(e) => setReferencia(e.target.value)} aria-label="Tiempo actual (su mejor marca)" />
          {!referencia.trim() && marcaSugerida != null && (
            <button type="button" className="mt-1 text-[11px] text-accent-soft hover:underline"
              onClick={() => setReferencia(toClock(marcaSugerida))}>
              Usar {toClock(marcaSugerida)} · su marca inscrita
            </button>
          )}
        </Field>
        <Field label="Brazadas en (m)"><input className="field" inputMode="numeric" value={tramoM} onChange={(e) => setTramoM(e.target.value)} aria-label="Metros del tramo en que se cuentan las brazadas" /></Field>
      </div>
      {!propMin && s?.proposed_effective && (
        <p className="-mt-2 text-[11px] text-text-faint">
          Sin Tiempo Pro: se compara con {toClock(s.proposed_effective[0], 0)}/{toClock(s.proposed_effective[1], 0)}, que sale de la intensidad y su tiempo actual.
        </p>
      )}

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

      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] text-text-faint">Solo el tiempo es obligatorio.</p>
        <SelectorDeColumnas vista={vista} />
      </div>
      <TablaDeLactato
        columnas={vista.columnas} filas={filas.length} celda={celda} marcada={(i) => avisadas.has(i)}
        pie={s && (
          <tr>
            <td colSpan={vista.columnas.length + 1} className="px-2 py-2 text-[12px] text-text-dim">
              Tiempo promedio <b className="mono text-text">{toClock(s.mean_time, 1)}</b>
              {s.pct_reference != null && <> · Intensidad <b className="mono text-text">{s.pct_reference.toFixed(1)} %</b></>}
              {' · '}CV {s.cv_pct.toFixed(1)} %
              {s.lactate_median != null && <> · lactato {s.lactate_median} mmol/L</>}
            </td>
          </tr>
        )}
      />

      {vista.recuperacion && (
        <div className="rounded-xl border border-line p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="label !mb-0">Recuperación</p>
            <button type="button" className="btn btn-ghost !px-2 !py-1 text-[11.5px]" onClick={otroMinuto}><Plus size={12} /> Minuto</button>
          </div>
          {recup.length === 0 ? (
            <p className="text-[11.5px] text-text-faint">Lactato y FC unos minutos después de la serie: el pico llega tarde (3, 5, 7, 10 min).</p>
          ) : recup.map((m, i) => (
            <div key={i} className="mb-1.5 flex items-center gap-1.5">
              <input className="field !w-16 !py-1" inputMode="decimal" value={m.minuto} onChange={(e) => editarRecup(i, 'minuto', e.target.value)} aria-label={`Recuperación ${i + 1}: minuto`} />
              <span className="text-[11px] text-text-faint">min</span>
              <input className="field !w-20 !py-1" inputMode="decimal" placeholder="FC" value={m.fc} onChange={(e) => editarRecup(i, 'fc', e.target.value)} aria-label={`Recuperación ${i + 1}: FC`} />
              <input className="field !w-20 !py-1" inputMode="decimal" placeholder="mmol/L" value={m.lactato} onChange={(e) => editarRecup(i, 'lactato', e.target.value)} aria-label={`Recuperación ${i + 1}: lactato`} />
              <button type="button" className="btn btn-ghost btn-icon !size-7" aria-label={`Quitar el minuto ${m.minuto}`} title="Quitar"
                onClick={() => setRecup((r) => r.filter((_, j) => j !== i))}><X size={12} /></button>
            </div>
          ))}
        </div>
      )}

      {analisis && analisis.warnings.length > 0 && (
        <div className="rounded-xl bg-surface-2 px-3 py-2.5 text-[12px]">
          {analisis.warnings.map((w) => (
            <p key={`${w.rep_number}-${w.field}`} className="flex gap-1.5 text-amber">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" /> #{filaDeRep(w.rep_number) + 1} · {w.message}
            </p>
          ))}
        </div>
      )}
      {errorDeAnalisis && <p className="text-[12px] text-coral">{(errorDeAnalisis as Error).message}</p>}
      <Field label="Notas"><textarea className="field min-h-14" maxLength={2000} value={notas} onChange={(e) => setNotas(e.target.value)} /></Field>

      <button className="btn btn-primary justify-center" disabled={!cuerpo || guardar.isPending} onClick={() => cuerpo && guardar.mutate(cuerpo)}>
        <Save size={14} /> {guardar.isPending ? 'Guardando…' : 'Guardar test'}
      </button>
    </div>
  )
}
