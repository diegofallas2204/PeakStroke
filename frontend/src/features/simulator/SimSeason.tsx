// Proyección ANUAL: la temporada son ~3 macrociclos encadenados con degradación,
// no un macro estirado. Techo de temporada contra el rango típico de la literatura.
import { CalendarClock } from 'lucide-react'
import type { SeasonResult } from '../../lib/types'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'
import { fraseDeTemporada, nivelLegible } from './simTextos'

const VERDICT: Record<string, { color: string; label: string }> = {
  ok: { color: '#34d399', label: 'Realista' },
  optimistic: { color: '#fbbf24', label: 'Optimista' },
  unrealistic: { color: '#fb7185', label: 'Poco realista' },
}

export function SimSeason({ season }: { season: SeasonResult }) {
  const v = VERDICT[season.verdict] ?? VERDICT.ok

  return (
    <Card title="Proyección anual · temporada de 3 macrociclos" className="card-hover" animate={false}>
      <div className="flex items-start gap-3.5">
        <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl"
          style={{ color: v.color, background: `${v.color}16`, border: `1px solid ${v.color}33` }}>
          <CalendarClock size={19} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <p className="display text-[14px] font-bold" style={{ color: v.color }}>
              Temporada: −{season.season_improvement_pct.toFixed(2)}%
            </p>
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider"
              style={{ color: v.color }}>{v.label}</span>
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider text-text-dim">
              {nivelLegible(season.level)}
            </span>
          </div>
          <p className="mt-1 text-[12px] leading-relaxed text-text-dim">{fraseDeTemporada(season)}</p>
          <p className="mono mt-0.5 text-[11px] text-text-faint">
            {toClock(season.season_start)} → {toClock(season.season_end)}
          </p>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-line pt-3.5 sm:gap-3">
        {season.macros.map((m) => (
          <div key={m.n_mac}>
            <p className="card-title !text-[9px]">Macro {m.n_mac}</p>
            <p className="mono mt-0.5 text-[15px] font-bold" style={{ color: v.color }}>
              −{m.improvement_pct.toFixed(2)}%
            </p>
            <p className="mono text-[10px] text-text-faint">
              {toClock(m.start_time)} → {toClock(m.end_time)}
            </p>
          </div>
        ))}
      </div>
    </Card>
  )
}
