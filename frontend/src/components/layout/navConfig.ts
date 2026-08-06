// Catálogo único de secciones. Lo consumen el rail de escritorio, el drawer
// móvil y la barra superior (para rotular la sección activa).
import {
  LayoutDashboard, CalendarRange, Users, Timer, Table2,
  ListChecks, GitCompareArrows, FlaskConical, UserRound, type LucideIcon,
} from 'lucide-react'
import { SECTION_ACCENT } from '../../lib/constants'

export type NavItem = { to: string; label: string; icon: LucideIcon; color: string }

const nav = (to: string, label: string, icon: LucideIcon): NavItem =>
  ({ to, label, icon, color: SECTION_ACCENT[to] })

export const NAV_ITEMS: NavItem[] = [
  nav('/', 'Dashboard', LayoutDashboard),
  nav('/macrociclos', 'Macrociclos', CalendarRange),
  nav('/atletas', 'Atletas', Users),
  nav('/pruebas', 'Base aeróbica', Timer),
  nav('/plan-semanal', 'Plan semanal', ListChecks),
  nav('/equipo', 'Tabla del equipo', Table2),
  nav('/comparacion', 'Comparación', GitCompareArrows),
  nav('/simulador', 'Simulador', FlaskConical),
]

// Perfil no está en NAV_ITEMS: vive en el pie del rail, no en la lista de
// secciones. Pero la barra superior de móvil sí necesita saber rotularlo.
export const PROFILE_ITEM: NavItem = nav('/perfil', 'Perfil', UserRound)

export function activeNavItem(pathname: string): NavItem {
  return [...NAV_ITEMS, PROFILE_ITEM].find((i) => i.to === pathname) ?? NAV_ITEMS[0]
}
