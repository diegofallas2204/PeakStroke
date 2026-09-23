// Proyección ANUAL: la temporada son ~3 macrociclos encadenados con degradación,
// no un macro estirado. Techo de temporada contra el rango típico de la literatura.
import { CalendarClock } from 'lucide-react'
import type { SeasonResult } from '../../lib/types'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'

const VERDICT: Record<string, { color: string; label: string }> = {
  ok: { color: '#34d399', label: 'Realista' },
  optimistic: { color: '#fbbf24', label: 'Optimista · techo' },
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
        <div className="flex-1">
          <div className="flex items-center gap-2.5">
            <p className="display text-[14px] font-bold" style={{ color: v.color }}>
              Temporada: −{season.season_improvement_pct.toFixed(2)}%
            </p>
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider"
              style={{ color: v.color }}>{v.label}</span>
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider text-text-dim">
              nivel {season.level}
            </span>
          </div>
          <p className="mt-1 text-[12px] leading-relaxed text-text-dim">{season.message}</p>
          <p className="mt-0.5 text-[11px] text-text-faint">
            Techo típico de la literatura para {season.level}:{' '}
            <span className="mono">{season.annual_low_pct}–{season.annual_high_pct}%</span> anual ·
            de <span className="mono text-text-dim">{toClock(season.season_start)}</span> a{' '}
            <span className="mono text-text-dim">{toClock(season.season_end)}</span>
          </p>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3 border-t border-line pt-3.5">
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
