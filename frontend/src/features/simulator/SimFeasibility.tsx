// Veredicto de factibilidad del macrociclo: si la meta cabe en el techo científico
// I_max y a qué ritmo obliga. El desglose numérico solo se pinta en modo completo.
import { FlaskConical, ShieldAlert, ShieldCheck, ShieldX, Waves, Zap } from 'lucide-react'
import type { Feasibility } from '../../lib/types'
import { toClock } from '../../lib/format'
import { Card } from '../../components/ui/primitives'

const FEAS = {
  ok: { icon: ShieldCheck, color: '#34d399', label: 'Objetivo realista' },
  warning: { icon: ShieldAlert, color: '#fbbf24', label: 'Exigente pero posible' },
  aggressive: { icon: ShieldX, color: '#fb7185', label: 'Objetivo agresivo' },
} as const

interface Props {
  feasibility: Feasibility
  /** Tiempo actual en segundos, para expresar la mejora total en porcentaje. */
  current: number | null
  goal: number | null
  simple: boolean
}

export function SimFeasibility({ feasibility, current, goal, simple }: Props) {
  const meta = FEAS[feasibility.status] ?? { icon: FlaskConical, color: '#8b93b8', label: '' }
  const Icon = meta.icon
  const color = meta.color

  return (
    <Card className="card-hover glow-edge" animate={false}>
      <div className="flex items-start gap-3.5">
        <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl"
          style={{ color, background: `${color}16`, border: `1px solid ${color}33` }}>
          <Icon size={19} />
        </span>
        <div className="flex-1">
          <div className="flex items-center gap-2.5">
            <p className="display text-[14px] font-bold" style={{ color }}>{meta.label}</p>
            <span className="flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider text-text-dim">
              {feasibility.tier === 1 ? <Waves size={10} /> : <Zap size={10} />}
              Tier {feasibility.tier} · {feasibility.tier === 1 ? 'aeróbico' : 'velocidad'}
            </span>
          </div>
          <p className="mt-1 text-[12px] leading-relaxed text-text-dim">{feasibility.message}</p>
        </div>
      </div>
      {!simple && (
        <div className="mt-4 grid grid-cols-4 gap-3 border-t border-line pt-3.5">
          <div>
            <p className="card-title !text-[9px]">Mejora total</p>
            <p className="mono mt-0.5 text-[15px] font-bold">
              {feasibility.improvement_total.toFixed(2)}s
              <span className="ml-1 text-[10px] text-text-faint">
                ({current ? ((feasibility.improvement_total / current) * 100).toFixed(1) : '—'}%)
              </span>
            </p>
          </div>
          <div>
            <p className="card-title !text-[9px]">Requerido / micro</p>
            <p className="mono mt-0.5 text-[15px] font-bold text-accent-soft">
              {feasibility.improvement_per_micro.toFixed(3)}s
            </p>
          </div>
          <div>
            <p className="card-title !text-[9px]">Ventana realista</p>
            <p className="mono mt-0.5 text-[15px] font-bold text-cyan">
              {feasibility.window_min != null
                ? `${feasibility.window_min.toFixed(2)}–${feasibility.window_max.toFixed(2)}s`
                : `≤ ${feasibility.window_max.toFixed(2)}s`}
            </p>
          </div>
          <div>
            <p className="card-title !text-[9px]">{feasibility.recommended_weeks ? 'Semanas sugeridas' : 'Tiempo final'}</p>
            <p className="mono mt-0.5 text-[15px] font-bold" style={{ color: feasibility.recommended_weeks ? 'var(--color-amber)' : 'var(--color-mint)' }}>
              {feasibility.recommended_weeks ?? toClock(goal ?? 0)}
            </p>
          </div>
        </div>
      )}
    </Card>
  )
}
