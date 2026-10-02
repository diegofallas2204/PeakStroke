// La celda de carga de la tabla del equipo: el balance (TSB) del atleta al
// cierre de la semana que se mira, con el aviso del día si lo hay.
//
// El número no se colorea por umbral —los umbrales viven solo en el backend—:
// el color sale del aviso que el backend ya decidió.
import type { LoadSnapshot } from '../../lib/types'
import { LOAD_ALERT_META, LOAD_REASON_LABEL } from '../../lib/constants'
import { signed, toDayMonth } from '../../lib/format'

export function CeldaDeCarga({ load }: { load: LoadSnapshot | null }) {
  if (!load) return <span className="text-[10.5px] text-text-faint">—</span>

  const meta = load.alert ? LOAD_ALERT_META[load.alert] : null
  const detalle = [
    `${toDayMonth(load.date)} · CTL ${load.ctl.toFixed(1)} · ATL ${load.atl.toFixed(1)}`,
    meta && `${meta.label}: ${load.reasons.map((r) => LOAD_REASON_LABEL[r] ?? r).join(' · ')}`,
    load.warming_up && 'Calentamiento: menos de dos semanas de historia, aún sin avisos',
  ].filter(Boolean).join('\n')

  return (
    <span className="inline-flex items-center gap-1.5" title={detalle}>
      <span
        className="size-2 shrink-0 rounded-full"
        style={{ background: meta?.color ?? 'var(--color-line-strong)' }}
        aria-hidden
      />
      <span className="mono font-semibold" style={meta ? { color: meta.color } : undefined}>
        {signed(load.tsb, 1)}
      </span>
      {meta && <span className="sr-only">{meta.label}</span>}
      {load.warming_up && <span className="text-[9.5px] text-text-faint">est.</span>}
    </span>
  )
}
