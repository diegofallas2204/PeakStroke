// Navegación lateral con indicador activo y chip del macrociclo en curso.
// El chip funciona como botón: abre el selector de macrociclo de trabajo.
import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutDashboard, CalendarRange, Users, Timer, Table2,
  ListChecks, GitCompareArrows, FlaskConical, Waves, ChevronsUpDown,
} from 'lucide-react'
import { api } from '../../lib/api'
import { useSelectedPlanId } from '../../hooks/useSelectedPlan'
import { MacroSwitcherModal } from '../../features/plans/MacroSwitcherModal'
import { ThemeSwitcher } from '../../features/settings/ThemeSwitcher'

const MAIN_NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/macrociclos', label: 'Macrociclos', icon: CalendarRange },
  { to: '/atletas', label: 'Atletas', icon: Users },
]

const ANALYSIS_NAV = [
  { to: '/pruebas', label: 'Base aeróbica', icon: Timer },
  { to: '/plan-semanal', label: 'Plan semanal', icon: ListChecks },
  { to: '/equipo', label: 'Tabla del equipo', icon: Table2 },
  { to: '/comparacion', label: 'Comparación', icon: GitCompareArrows },
  { to: '/simulador', label: 'Simulador', icon: FlaskConical },
]

function NavSection({ title, items }: { title: string; items: typeof MAIN_NAV }) {
  return (
    <>
      <p className="mt-5 mb-1.5 px-5 text-[9.5px] font-bold uppercase tracking-[0.16em] text-text-faint">
        {title}
      </p>
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            `group relative mx-2.5 flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-[12.5px] font-medium transition-all duration-200 ${
              isActive
                ? 'bg-[rgba(59,130,246,.13)] text-accent-soft'
                : 'text-text-dim hover:bg-surface-2 hover:text-text'
            }`
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <span
                  className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full"
                  style={{ background: 'linear-gradient(180deg,#3b82f6,#22d3ee)' }}
                />
              )}
              <Icon size={15.5} strokeWidth={2.1} className="shrink-0 transition-transform duration-200 group-hover:scale-110" />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </>
  )
}

export function Sidebar() {
  const selectedId = useSelectedPlanId()
  const [switcherOpen, setSwitcherOpen] = useState(false)
  const { data: summary } = useQuery({
    queryKey: ['dashboard', selectedId],
    queryFn: () => api.dashboard.summary(selectedId ?? undefined),
    retry: false,
  })

  return (
    <aside className="relative z-10 flex w-[228px] shrink-0 flex-col border-r border-line bg-[var(--color-sidebar)] backdrop-blur-xl">
      <div className="flex items-center gap-2.5 px-5 pb-5 pt-6">
        <span
          className="flex size-9 items-center justify-center rounded-xl"
          style={{ background: 'linear-gradient(135deg,rgba(59,130,246,.25),rgba(34,211,238,.18))', border: '1px solid rgba(59,130,246,.3)' }}
        >
          <Waves size={18} className="text-accent-soft" />
        </span>
        <div>
          <p className="display text-[15.5px] font-bold leading-none tracking-tight">
            Peak<span className="text-accent-soft">Stroke</span>
          </p>
          <p className="mt-1 text-[9px] uppercase tracking-[0.22em] text-text-faint">
            Performance Planner
          </p>
        </div>
      </div>

      {summary && (
        <button
          type="button"
          onClick={() => setSwitcherOpen(true)}
          className="card card-hover mx-3 px-3.5 py-3 text-left transition-all"
          data-animate
          aria-label="Cambiar macrociclo de trabajo"
        >
          <div className="flex items-center justify-between gap-1.5">
            <span className="flex items-center gap-1.5">
              <span className="pulse-dot size-1.5 rounded-full bg-mint" />
              <span className="text-[9px] font-bold uppercase tracking-[0.15em] text-text-faint">
                Macrociclo de trabajo
              </span>
            </span>
            <ChevronsUpDown size={13} className="text-text-faint" />
          </div>
          <p className="mt-1 truncate text-[12.5px] font-semibold">{summary.plan_name}</p>
          <p className="mt-0.5 text-[10.5px] text-text-dim">
            Semana {summary.current_week ?? '—'} / {summary.total_weeks} · {summary.athletes_total} atletas
          </p>
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-3">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${((summary.current_week ?? 0) / summary.total_weeks) * 100}%`,
                background: 'linear-gradient(90deg,#3b82f6,#22d3ee)',
              }}
            />
          </div>
        </button>
      )}

      <MacroSwitcherModal open={switcherOpen} onClose={() => setSwitcherOpen(false)} />

      <nav className="flex-1 overflow-y-auto pb-4">
        <NavSection title="Principal" items={MAIN_NAV} />
        <NavSection title="Análisis" items={ANALYSIS_NAV} />
      </nav>

      <footer className="border-t border-line px-5 py-3.5">
        <ThemeSwitcher />
        <p className="mt-3.5 text-[9.5px] text-text-faint">v0.1 · local-first</p>
      </footer>
    </aside>
  )
}
