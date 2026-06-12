// Línea de tiempo horizontal de fases del macrociclo con marcador de semana
// actual y banderas de competencia.
import { Flag } from 'lucide-react'
import type { DashboardSummary } from '../../lib/types'

export function PhaseStrip({
  phases, totalWeeks, currentWeek, competitions,
}: {
  phases: DashboardSummary['phases']
  totalWeeks: number
  currentWeek: number | null
  competitions: DashboardSummary['competitions']
}) {
  return (
    <div>
      <div className="relative flex h-12 w-full gap-[3px] overflow-visible">
        {phases.map((phase) => {
          const span = phase.week_end - phase.week_start + 1
          return (
            <div
              key={phase.name + phase.week_start}
              className="group relative flex items-center justify-center rounded-lg transition-all duration-300"
              style={{
                flex: span,
                background: phase.is_current ? `${phase.color}33` : `${phase.color}14`,
                border: `1px solid ${phase.is_current ? `${phase.color}88` : `${phase.color}30`}`,
                boxShadow: phase.is_current ? `0 0 24px -6px ${phase.color}66` : undefined,
              }}
            >
              <div className="text-center">
                <p className="text-[10.5px] font-bold uppercase tracking-wider" style={{ color: phase.color }}>
                  {phase.name}
                </p>
                <p className="text-[9px] text-text-faint">
                  S{phase.week_start}–S{phase.week_end}
                </p>
              </div>
            </div>
          )
        })}
        {currentWeek && (
          <div
            className="pointer-events-none absolute -top-1 bottom-[-4px] w-[2px] rounded-full"
            style={{
              left: `${((currentWeek - 0.5) / totalWeeks) * 100}%`,
              background: 'linear-gradient(180deg,#fbbf24,transparent)',
            }}
          >
            <span className="absolute -top-0.5 left-1/2 size-2 -translate-x-1/2 rounded-full bg-amber" style={{ boxShadow: '0 0 10px #fbbf24' }} />
          </div>
        )}
      </div>
      {competitions.length > 0 && (
        <div className="relative mt-2 h-5">
          {competitions.map((comp) => (
            <div
              key={comp.name}
              className="absolute flex -translate-x-1/2 items-center gap-1"
              style={{ left: `${((comp.week_number - 0.5) / totalWeeks) * 100}%` }}
              title={`${comp.name} · ${comp.days} día(s)`}
            >
              <Flag size={11} className={comp.is_main ? 'text-amber' : 'text-text-dim'} />
              <span className={`whitespace-nowrap text-[9.5px] font-semibold ${comp.is_main ? 'text-amber' : 'text-text-dim'}`}>
                {comp.name}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
