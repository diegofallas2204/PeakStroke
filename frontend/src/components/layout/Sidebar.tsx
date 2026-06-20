import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutDashboard, CalendarRange, Users, Timer, Table2,
  ListChecks, GitCompareArrows, FlaskConical, ChevronsUpDown,
  Settings, type LucideIcon,
} from 'lucide-react'
import { Manta } from '../ui/Manta'
import { api } from '../../lib/api'
import { SECTION_ACCENT } from '../../lib/constants'
import { useSelectedPlanId } from '../../hooks/useSelectedPlan'
import { MacroSwitcherModal } from '../../features/plans/MacroSwitcherModal'
import { ThemeSwitcher } from '../../features/settings/ThemeSwitcher'
import { Modal } from '../ui/primitives'

type NavItem = { to: string; label: string; icon: LucideIcon; color: string }

const nav = (to: string, label: string, icon: LucideIcon): NavItem =>
  ({ to, label, icon, color: SECTION_ACCENT[to] })

const NAV_ITEMS: NavItem[] = [
  nav('/', 'Dashboard', LayoutDashboard),
  nav('/macrociclos', 'Macrociclos', CalendarRange),
  nav('/atletas', 'Atletas', Users),
  nav('/pruebas', 'Base aeróbica', Timer),
  nav('/plan-semanal', 'Plan semanal', ListChecks),
  nav('/equipo', 'Tabla del equipo', Table2),
  nav('/comparacion', 'Comparación', GitCompareArrows),
  nav('/simulador', 'Simulador', FlaskConical),
]

function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} title="Ajustes">
      <div className="flex flex-col gap-5 py-1">
        <div>
          <p className="card-title mb-3">Apariencia</p>
          <ThemeSwitcher />
        </div>
        <p className="text-[9px] text-text-faint">PeakStroke v0.1 · local-first</p>
      </div>
    </Modal>
  )
}

export function Sidebar() {
  const selectedId = useSelectedPlanId()
  const [switcherOpen, setSwitcherOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const { data: summary } = useQuery({
    queryKey: ['dashboard', selectedId],
    queryFn: () => api.dashboard.summary(selectedId ?? undefined),
    retry: false,
  })

  return (
    // Wrapper reserves the collapsed width so the main content never shifts.
    <div className="relative z-20 w-14 shrink-0">
      <aside
        className={[
          'group/aside absolute inset-y-0 left-0 flex flex-col overflow-hidden',
          'border-r border-line bg-[var(--color-sidebar)] backdrop-blur-xl',
          'w-14 transition-[width] duration-300 ease-in-out hover:w-[228px]',
        ].join(' ')}
      >
        {/* ── Logo ───────────────────────────────────────────── */}
        <div className="flex shrink-0 items-center gap-2.5 overflow-hidden px-[13px] pb-4 pt-6">
          <span
            className="flex size-9 shrink-0 items-center justify-center rounded-xl"
            style={{
              background: 'linear-gradient(135deg,rgba(59,130,246,.18),rgba(34,211,238,.12))',
              border: '1px solid rgba(59,130,246,.25)',
            }}
          >
            <Manta size={26} />
          </span>
          {/* Visible only when expanded */}
          <div className="overflow-hidden whitespace-nowrap opacity-0 transition-opacity delay-100 duration-200 group-hover/aside:opacity-100">
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

        {/* ── Macrociclo activo — compacto ────────────────────── */}
        {summary && (
          <div className="mx-2 mb-1 shrink-0">
            <button
              type="button"
              onClick={() => setSwitcherOpen(true)}
              aria-label="Cambiar macrociclo de trabajo"
              className={[
                'flex w-full items-center gap-2.5 rounded-[10px] py-[9px]',
                'px-1.5 group-hover/aside:px-3',
                'border border-transparent bg-transparent',
                'group-hover/aside:border-[rgba(59,130,246,.15)] group-hover/aside:bg-[rgba(59,130,246,.07)]',
                'transition-[background-color,border-color,padding] duration-300 ease-in-out',
              ].join(' ')}
            >
              {/* Dot — siempre visible; caja azul solo cuando está expandido */}
              <span className="flex size-[28px] shrink-0 items-center justify-center rounded-lg bg-transparent transition-[background-color] duration-300 group-hover/aside:bg-[rgba(59,130,246,.15)]">
                <span className="pulse-dot size-[7px] rounded-full bg-mint" />
              </span>

              {/* Plan info — visible only when expanded */}
              <div className="min-w-0 flex-1 overflow-hidden opacity-0 transition-opacity delay-100 duration-200 group-hover/aside:opacity-100">
                <p className="text-[8.5px] font-bold uppercase tracking-[0.14em] text-text-faint leading-none">
                  Macrociclo activo
                </p>
                <p className="mt-[3px] truncate text-left text-[12px] font-semibold leading-none">
                  {summary.plan_name}
                </p>
              </div>
              <ChevronsUpDown
                size={11}
                className="shrink-0 text-text-faint opacity-0 transition-opacity delay-100 duration-200 group-hover/aside:opacity-100"
              />
            </button>
          </div>
        )}

        {/* ── Nav items — flat, sin secciones ─────────────────── */}
        <nav className="flex-1 py-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, color }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={({ isActive }) =>
                ({
                  '--nav-item-color': color,
                  ...(isActive ? { background: `${color}16`, color } : {}),
                } as React.CSSProperties)
              }
              className={({ isActive }) =>
                `nav-item relative mx-2 flex items-center gap-2.5 rounded-[10px] px-1.5 py-[9px] text-[12.5px] font-medium transition-[background-color,color,padding] duration-300 ease-in-out group-hover/aside:px-3 ${
                  isActive ? 'nav-item--active' : 'text-text-dim'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span
                      className="nav-indicator absolute -left-2 top-[calc(50%-10px)] h-5 w-[3px] rounded-r-full"
                      style={{ background: color, boxShadow: `0 0 10px 2px ${color}55` }}
                    />
                  )}
                  <span
                    className="flex size-[28px] shrink-0 items-center justify-center rounded-lg transition-colors duration-200"
                    style={isActive ? { background: `${color}20` } : {}}
                  >
                    <Icon size={14.5} strokeWidth={2.1} />
                  </span>
                  {/* Label — visible only when expanded */}
                  <span className="overflow-hidden whitespace-nowrap leading-none opacity-0 transition-opacity delay-[80ms] duration-200 group-hover/aside:opacity-100">
                    {label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* ── Bottom — gear de ajustes ─────────────────────────── */}
        <div className="shrink-0 border-t border-line px-2 py-2.5">
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="nav-item flex w-full items-center gap-2.5 rounded-[10px] px-1.5 py-[9px] text-[12.5px] font-medium text-text-dim transition-[background-color,color,padding] duration-300 ease-in-out group-hover/aside:px-3"
            style={{ '--nav-item-color': 'var(--color-text-dim)' } as React.CSSProperties}
          >
            <span className="flex size-[28px] shrink-0 items-center justify-center rounded-lg">
              <Settings size={14.5} strokeWidth={2.1} />
            </span>
            <span className="overflow-hidden whitespace-nowrap leading-none opacity-0 transition-opacity delay-[80ms] duration-200 group-hover/aside:opacity-100">
              Ajustes
            </span>
          </button>
        </div>
      </aside>

      <MacroSwitcherModal open={switcherOpen} onClose={() => setSwitcherOpen(false)} />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
