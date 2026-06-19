import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutDashboard, CalendarRange, Users, Timer, Table2,
  ListChecks, GitCompareArrows, FlaskConical, Waves, ChevronsUpDown,
  type LucideIcon,
} from 'lucide-react'
import { api } from '../../lib/api'
import { SECTION_ACCENT } from '../../lib/constants'
import { useSelectedPlanId } from '../../hooks/useSelectedPlan'
import { MacroSwitcherModal } from '../../features/plans/MacroSwitcherModal'
import { ThemeSwitcher } from '../../features/settings/ThemeSwitcher'

type NavItem = { to: string; label: string; icon: LucideIcon; color: string }

const item = (to: string, label: string, icon: LucideIcon): NavItem =>
  ({ to, label, icon, color: SECTION_ACCENT[to] })

const MAIN_NAV: NavItem[] = [
  item('/', 'Dashboard', LayoutDashboard),
  item('/macrociclos', 'Macrociclos', CalendarRange),
  item('/atletas', 'Atletas', Users),
]

const ANALYSIS_NAV: NavItem[] = [
  item('/pruebas', 'Base aeróbica', Timer),
  item('/plan-semanal', 'Plan semanal', ListChecks),
  item('/equipo', 'Tabla del equipo', Table2),
  item('/comparacion', 'Comparación', GitCompareArrows),
  item('/simulador', 'Simulador', FlaskConical),
]

function NavSection({ title, items }: { title: string; items: NavItem[] }) {
  return (
    <>
      <p className="mt-5 mb-1.5 px-5 flex items-center gap-2 text-[9px] font-bold uppercase tracking-[0.18em] text-text-faint">
        <span className="inline-block h-px w-3 shrink-0 rounded-full bg-line-strong" />
        {title}
      </p>
      {items.map(({ to, label, icon: Icon, color }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          style={({ isActive }) => ({
            '--nav-item-color': color,
            ...(isActive ? { background: `${color}16`, color } : {}),
          } as React.CSSProperties)}
          className={({ isActive }) =>
            `nav-item group relative mx-2.5 flex items-center gap-2.5 rounded-[10px] px-3 py-[9px] text-[12.5px] font-medium transition-all duration-200 ${
              isActive ? 'nav-item--active' : 'text-text-dim'
            }`
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <span
                  className="nav-indicator absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full"
                  style={{ background: color, boxShadow: `0 0 10px 2px ${color}55` }}
                />
              )}
              <span
                className="flex size-[28px] shrink-0 items-center justify-center rounded-lg transition-all duration-200"
                style={isActive ? { background: `${color}20` } : {}}
              >
                <Icon size={14.5} strokeWidth={2.1} />
              </span>
              <span className="flex-1 leading-none">{label}</span>
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
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 pb-5 pt-6">
        <span
          className="flex size-9 items-center justify-center rounded-xl"
          style={{
            background: 'linear-gradient(135deg,rgba(59,130,246,.25),rgba(34,211,238,.18))',
            border: '1px solid rgba(59,130,246,.3)',
          }}
        >
          <Waves size={18} className="text-accent-soft" />
        </span>
        <div>
          <p className="display text-[15.5px] font-bold leading-none tracking-tight">
            Peak
            <span
              style={{
                background: 'linear-gradient(135deg,#3b82f6,#22d3ee)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              Stroke
            </span>
          </p>
          <p className="mt-1 text-[9px] uppercase tracking-[0.22em] text-text-faint">
            Performance Planner
          </p>
        </div>
      </div>

      {/* Macro activo */}
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
                Macrociclo activo
              </span>
            </span>
            <ChevronsUpDown size={12} className="text-text-faint" />
          </div>
          <p className="mt-1.5 truncate text-[12.5px] font-semibold leading-tight">{summary.plan_name}</p>
          <p className="mt-0.5 text-[10.5px] text-text-dim">
            Sem. {summary.current_week ?? '—'}/{summary.total_weeks} · {summary.athletes_total} atletas
          </p>
          <div className="mt-2.5 h-[3px] overflow-hidden rounded-full bg-surface-3">
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
        <p className="mt-3.5 text-[9px] text-text-faint">v0.1 · local-first</p>
      </footer>
    </aside>
  )
}
