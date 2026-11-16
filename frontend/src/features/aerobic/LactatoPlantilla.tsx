// Un test guardado, con la forma de la plantilla del entrenador: la cabecera,
// la tabla (mismas columnas ocultables que al apuntarlo) y el pie con el
// promedio, la intensidad y la recuperación. Todo lo calculado viene del backend.
import { Calculator } from 'lucide-react'
import type { LactateTest } from '../../lib/types'
import { STROKE_LABEL } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'
import { Calculado, SelectorDeColumnas, TablaDeLactato } from './TablaDeLactato'
import { COLOR_DE_ESTADO, useColumnasDeLactato, type ClaveDeColumna } from './lactatoColumnas'

export function LactatoPlantilla({ test, nombre, edad }: { test: LactateTest; nombre?: string; edad?: number | null }) {
  const vista = useColumnasDeLactato()
  const s = test.summary
  const avisadas = new Set(test.warnings.map((w) => w.rep_number - 1))
  const dudosa = (i: number, campo: 'tiempo' | 'lactato' | 'fc') =>
    test.warnings.some((w) => w.rep_number === i + 1 && w.field === campo)
  const propuesto = test.proposed_min != null && test.proposed_max != null
    ? `${toClock(test.proposed_min, 0)}/${toClock(test.proposed_max, 0)}`
    : s.proposed_effective ? `${toClock(s.proposed_effective[0], 0)}/${toClock(s.proposed_effective[1], 0)} (calculado)` : '—'

  const cabecera: [string, string][] = [
    ['Nombre', nombre ?? '—'],
    ['Edad', edad != null ? `${edad} años` : '—'],
    ['Capacidad', test.target_zone],
    ['Prueba', `${test.reps.length}×${test.rep_distance}`],
    ['Técnica', test.stroke ? STROKE_LABEL[test.stroke] ?? test.stroke : '—'],
    ['Piscina', test.pool_length ? `${test.pool_length} m` : '—'],
    ['Tiempo Pro', propuesto],
    ['Intens. Pro', test.proposed_intensity_min != null ? `${test.proposed_intensity_min}–${test.proposed_intensity_max} %` : '—'],
    ['Pausas', test.rest_s != null ? `${test.rest_type === 'salida' ? 'salida ' : ''}${test.rest_s < 60 ? `${test.rest_s} s` : toClock(test.rest_s, 0)}` : '—'],
    ['Tiempo Actual', test.reference_time != null ? toClock(test.reference_time) : '—'],
  ]

  const texto = (v: string | number | null | undefined, rojo = false) => (
    <span className={`mono px-1 ${rojo ? 'rounded border border-dashed border-amber' : ''}`}>{v ?? '—'}</span>
  )
  const celda = (clave: ClaveDeColumna, i: number) => {
    const r = test.reps[i]
    switch (clave) {
      case 'serie': return texto(r.series)
      case 'tiempo': return texto(toClock(r.swim_time, 0), dudosa(i, 'tiempo'))
      case 'intensidad': return texto(r.effort)
      case 'velocidad': return <Calculado valor={r.speed} />
      case 'lactato': return (
        <span className={`mono px-1 font-semibold ${dudosa(i, 'lactato') ? 'rounded border border-dashed border-amber' : ''}`}
          style={{ color: r.lactate_zone ? COLOR_DE_ESTADO[r.lactate_zone] : undefined }}>
          {r.lactate ?? '—'}
        </span>
      )
      case 'fc': return texto(r.heart_rate, dudosa(i, 'fc'))
      case 'frecuencia': return <Calculado valor={r.cycle_rate} decimales={1} />
      case 'brazadas': return texto(r.stroke_counts.length ? r.stroke_counts.join(', ') : null)
      case 'efectividad': return <Calculado valor={r.m_per_cycle} />
      case 'metros': return <Calculado valor={r.m_per_stroke} />
      case 'parciales': return texto(r.splits.length ? r.splits.map((p) => toClock(p, 1)).join(' · ') : null)
      case 'tramo': return texto(r.segment_time != null ? toClock(r.segment_time, 1) : null)
    }
  }

  return (
    <Card className="!p-4" title="Plantilla" action={<SelectorDeColumnas vista={vista} />}>
      <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px] sm:grid-cols-5">
        {cabecera.map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="text-[10px] uppercase tracking-wider text-text-faint">{k}</dt>
            <dd className="truncate font-semibold">{v}</dd>
          </div>
        ))}
      </dl>
      <TablaDeLactato
        columnas={vista.columnas} filas={test.reps.length} celda={celda} marcada={(i) => avisadas.has(i)}
        pie={(
          <tr>
            <td colSpan={vista.columnas.length + 1} className="px-2 py-2 text-[12px] text-text-dim">
              Tiempo promedio <b className="mono text-text">{toClock(s.mean_time, 1)}</b>
              {s.pct_reference != null && (
                <> · Intensidad <b className="mono" style={{ color: s.intensity_state ? COLOR_DE_ESTADO[s.intensity_state] : undefined }}>{s.pct_reference.toFixed(1)} %</b></>
              )}
              {' · '}CV {s.cv_pct.toFixed(1)} %
              {s.stroke_index != null && <> · índice de ciclo {s.stroke_index.toFixed(2)}</>}
            </td>
          </tr>
        )}
      />
      <p className="mt-1.5 flex items-center gap-1 text-[10.5px] text-text-faint">
        <Calculator size={10} /> calculado por la app · borde punteado: dato a revisar · lactato en color según la zona
      </p>

      {vista.recuperacion && test.recovery.length > 0 && (
        <div className="mt-4">
          <p className="label">Recuperación</p>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="bg-surface-2 text-[10px] uppercase tracking-wider text-text-faint">
                  <th className="px-2 py-1.5 text-left">Tiempo recup. (min)</th>
                  <th className="px-2 py-1.5 text-left">FC (lat/min)</th>
                  <th className="px-2 py-1.5 text-left">Lactato (mmol/L)</th>
                </tr>
              </thead>
              <tbody>
                {test.recovery.map((m) => (
                  <tr key={m.minute} className="border-t border-line">
                    <td className="mono px-2 py-1">{m.minute}</td>
                    <td className="mono px-2 py-1">{m.heart_rate ?? '—'}</td>
                    <td className={`mono px-2 py-1 ${s.recovery_peak?.[0] === m.minute ? 'font-bold text-coral' : ''}`}>{m.lactate ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  )
}
