// Navegación entre secciones. Dos presentaciones del mismo dashboard:
//   · ≥ lg  → riel de 56px anclado a la izquierda que se despliega al hover
//   · < lg  → barra superior con botón de menú y drawer desplegable (MobileNav)
// El estado de los modales (macrociclo, ajustes) vive aquí para que ambas
// presentaciones compartan una sola instancia.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { useSelectedPlanId } from '../../hooks/useSelectedPlan'
import { MacroSwitcherModal } from '../../features/plans/MacroSwitcherModal'
import { NavBrand, NavFooter, NavLinks, NavPlanButton } from './NavContent'
import { MobileNav } from './MobileNav'
import { SettingsModal } from './SettingsModal'

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
    // El wrapper reserva el ancho colapsado en escritorio (para que el contenido
    // nunca salte) y ocupa el alto de la barra superior en móvil.
    <div className="relative z-20 w-full shrink-0 lg:w-14">
      <MobileNav
        planName={summary?.plan_name}
        onOpenSwitcher={() => setSwitcherOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <aside
        className={[
          'group/aside absolute inset-y-0 left-0 hidden flex-col overflow-hidden lg:flex',
          'border-r border-line bg-[var(--color-sidebar)] backdrop-blur-xl',
          'w-14 transition-[width] duration-300 ease-in-out hover:w-[228px]',
        ].join(' ')}
      >
        <NavBrand variant="rail" />
        {summary && (
          <NavPlanButton
            variant="rail"
            planName={summary.plan_name}
            onClick={() => setSwitcherOpen(true)}
          />
        )}
        <NavLinks variant="rail" />
        <NavFooter variant="rail" onOpenSettings={() => setSettingsOpen(true)} />
      </aside>

      <MacroSwitcherModal open={switcherOpen} onClose={() => setSwitcherOpen(false)} />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
