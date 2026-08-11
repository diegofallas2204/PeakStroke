// Parámetros del simulador: la fila superior de controles y su estado.
// El estado vive en la página (lo consumen las consultas), pero la forma de
// editarlo —y las dos reglas de autocorrección— viven aquí.
import {
  CURVES, DISTANCES, POOLS, SPECIALTIES,
  coerceStroke, specialtyForDistance, strokeOptionsForDistance,
} from '../../lib/constants'
import { Card, Field } from '../../components/ui/primitives'
import type { SimParamsState } from './simDefaults'

interface Props {
  params: SimParamsState
  setParams: React.Dispatch<React.SetStateAction<SimParamsState>>
  /** El tiempo meta debe ser menor al actual; si no, se avisa y no se consulta. */
  valid: boolean
}

export function SimParams({ params, setParams, valid }: Props) {
  const set = (key: keyof SimParamsState, numeric = false) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setParams((p) => ({ ...p, [key]: numeric ? Number(e.target.value) : e.target.value }))

  return (
    <Card title="Parámetros del plan" className="card-hover">
      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-5">
        <Field label="Distancia">
          <select className="field" value={params.distance}
            onChange={(e) => {
              const distance = Number(e.target.value)
              // Autocorrige el estilo si la distancia lo invalida (p. ej. 400 mariposa → libre)
              // y autoselecciona la especialidad sugerida por la prueba (el coach puede cambiarla).
              setParams((p) => ({
                ...p, distance,
                stroke: coerceStroke(distance, p.stroke),
                specialty: specialtyForDistance(distance),
              }))
            }}>
            {DISTANCES.map((d) => <option key={d} value={d}>{d}m</option>)}
          </select>
        </Field>
        <Field label="Estilo">
          <select className="field" value={params.stroke} onChange={set('stroke')}>
            {strokeOptionsForDistance(params.distance).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>
        <Field label="Tiempo actual">
          <input className="field mono" value={params.current} onChange={set('current')} />
        </Field>
        <Field label="Tiempo meta">
          <input className="field mono" value={params.goal} onChange={set('goal')} />
        </Field>
        <Field label="Semanas">
          <input type="number" className="field" value={params.weeks} min={4} max={30} onChange={set('weeks', true)} />
        </Field>
        <Field label="Micro (sem)">
          <select className="field" value={params.micro} onChange={set('micro', true)}>
            <option value={4}>4</option><option value={5}>5</option>
          </select>
        </Field>
        <Field label="Km totales">
          <input type="number" className="field" value={params.km} min={50} max={1500} step={10} onChange={set('km', true)} />
        </Field>
        <Field label="Curva">
          <select className="field" value={params.curve} onChange={set('curve')}>
            {CURVES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </Field>
        <Field label="Piscina">
          <select className="field" value={params.pool} onChange={set('pool')}>
            {POOLS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </Field>
        <Field label="Especialidad (auto)" className="col-span-2 sm:col-span-1">
          <select className="field" value={params.specialty} onChange={set('specialty')}
            title="Sugerida por la distancia de la prueba — puedes cambiarla.">
            {SPECIALTIES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>
      </div>
      {!valid && (
        <p className="mt-3 text-[11px] text-coral">
          El tiempo meta debe ser menor al actual (formato m:ss.cc).
        </p>
      )}
    </Card>
  )
}
