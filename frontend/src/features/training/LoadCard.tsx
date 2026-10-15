// El estado de carga del atleta: cómo está hoy, la curva del rango y los
// episodios en los que el sistema avisó.
import { Link } from 'react-router-dom'
import { AlertTriangle, Timer } from 'lucide-react'
import type { LoadDay, TrainingLoad } from '../../lib/types'
import { LOAD_ALERT_META, LOAD_REASON_LABEL } from '../../lib/constants'
import { signed, toDayMonth } from '../../lib/format'
import { Card } from '../../components/ui/primitives'
import { LoadChart } from './LoadChart'
import { SERIES } from './series'

type Episodio = { desde: string; hasta: string; nivel: 'advertencia' | 'peligro'; motivos: string[] }

/**
 * Días seguidos con aviso → un episodio. Solo agrupa lo que el backend marcó:
 * no decide nada. El nivel del episodio es el peor de sus días.
 */
function episodios(days: LoadDay[]): Episodio[] {
  const out: Episodio[] = []
  let actual: Episodio | null = null
  let ayer: string | null = null
  for (const d of days) {
    const seguido = ayer != null && actual != null && esElDiaSiguiente(ayer, d.date)
    if (d.alert) {
      if (actual && seguido) {
        actual.hasta = d.date
        if (d.alert === 'peligro') actual.nivel = 'peligro'
        for (const r of d.reasons) if (!actual.motivos.includes(r)) actual.motivos.push(r)
      } else {
        actual = { desde: d.date, hasta: d.date, nivel: d.alert, motivos: [...d.reasons] }
        out.push(actual)
      }
    } else {
      actual = null
    }
    ayer = d.date
  }
  return out
}

function esElDiaSiguiente(a: string, b: string): boolean {
  const [y, m, d] = a.split('-').map(Number)
  const siguiente = new Date(y, m - 1, d + 1)
  const [y2, m2, d2] = b.split('-').map(Number)
  return siguiente.getTime() === new Date(y2, m2 - 1, d2).getTime()
}

function Stat({ label, value, color, sub }: { label: string; value: string; color: string; sub?: string }) {
  return (
    <Card className="card-hover">
      <p className="card-title">{label}</p>
      <p className="display mt-1.5 text-[26px] font-bold" style={{ color }}>{value}</p>
      {sub && <p className="text-[10.5px] text-text-faint">{sub}</p>}
    </Card>
  )
}

export function LoadCard({ load }: { load: TrainingLoad }) {
  const hoy = load.days[load.days.length - 1]
  const lista = episodios(load.days).reverse().slice(0, 5)

  return (
    <div className="flex flex-col gap-4">
      {load.sessions_without_css > 0 && (
        <p className="flex items-start gap-2 rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 text-[11.5px] text-amber">
          <Timer size={14} className="mt-px shrink-0" />
          <span>
            {load.sessions_without_css === 1 ? 'Hay 1 sesión' : `Hay ${load.sessions_without_css} sesiones`} anterior
            {load.sessions_without_css === 1 ? '' : 'es'} al primer test aeróbico: sin CSS no tienen carga y no entran en la curva.{' '}
            <Link to="/pruebas" className="underline underline-offset-2">Registrar un test</Link>
          </span>
        </p>
      )}

      {hoy && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Stat label={SERIES.ctl.label} value={hoy.ctl.toFixed(1)} color={SERIES.ctl.color} sub="La forma de fondo: lo que el cuerpo tolera" />
          <Stat label={SERIES.atl.label} value={hoy.atl.toFixed(1)} color={SERIES.atl.color} sub="La fatiga de los últimos días" />
          <Stat
            label={SERIES.tsb.label} value={signed(hoy.tsb, 1)} color={SERIES.tsb.color}
            sub={load.warming_up
              ? 'Aún estimando el arranque: sin alertas'
              : hoy.alert ? `${LOAD_ALERT_META[hoy.alert].label} hoy` : 'Sin aviso hoy'}
          />
        </div>
      )}

      <Card
        title="Carga de entrenamiento · Banister"
        className="card-hover"
        action={(
          <div className="hidden flex-wrap items-center gap-3 text-[10.5px] text-text-dim md:flex">
            {(Object.keys(SERIES) as (keyof typeof SERIES)[]).map((k) => (
              <span key={k} className="flex items-center gap-1.5">
                <span className="size-2 rounded-full" style={{ background: SERIES[k].color }} />
                {SERIES[k].label}
              </span>
            ))}
          </div>
        )}
      >
        {load.days.length ? (
          <LoadChart load={load} />
        ) : (
          <p className="py-10 text-center text-xs text-text-dim">
            Sin carga en este rango. La curva empieza con la primera sesión posterior a un test aeróbico.
          </p>
        )}
      </Card>

      {lista.length > 0 && (
        <Card title="Avisos en el rango" className="card-hover">
          <ul className="flex flex-col gap-2">
            {lista.map((e) => (
              <li key={e.desde} className="flex items-start gap-2.5 text-[12px]">
                <AlertTriangle size={14} className="mt-px shrink-0" style={{ color: LOAD_ALERT_META[e.nivel].color }} />
                <span>
                  <span className="font-semibold">
                    {e.desde === e.hasta ? toDayMonth(e.desde) : `${toDayMonth(e.desde)} – ${toDayMonth(e.hasta)}`}
                  </span>
                  <span style={{ color: LOAD_ALERT_META[e.nivel].color }}> · {LOAD_ALERT_META[e.nivel].label}</span>
                  <span className="text-text-dim"> · {e.motivos.map((m) => LOAD_REASON_LABEL[m] ?? m).join(' · ')}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
