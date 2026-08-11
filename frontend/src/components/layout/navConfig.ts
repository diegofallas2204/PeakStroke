// Catálogo único de secciones. Lo consumen el rail de escritorio, el drawer
// móvil, la barra superior (para rotular la sección activa) y las guardas de
// ruta de `App.tsx`.
//
// Que las rutas y los permisos vivan en la MISMA lista es deliberado: esconder
// una sección del menú no la hace inalcanzable —`/equipo` se puede teclear— así
// que si el filtro del menú y el de las rutas fueran dos listas, tarde o
// temprano dirían cosas distintas.
import {
  LayoutDashboard, CalendarRange, Users, Timer, Table2,
  ListChecks, GitCompareArrows, FlaskConical, UserRound, type LucideIcon,
} from 'lucide-react'
import { SECTION_ACCENT } from '../../lib/constants'

export type Role = 'coach' | 'athlete'

export type NavItem = {
  to: string
  label: string
  icon: LucideIcon
  color: string
  /** Roles que ven la sección. Sin `roles`, la ven todos. */
  roles?: Role[]
}

const nav = (to: string, label: string, icon: LucideIcon, roles?: Role[]): NavItem =>
  ({ to, label, icon, color: SECTION_ACCENT[to], roles })

export const NAV_ITEMS: NavItem[] = [
  nav('/', 'Dashboard', LayoutDashboard),
  nav('/macrociclos', 'Macrociclos', CalendarRange, ['coach']),
  nav('/atletas', 'Atletas', Users, ['coach']),
  nav('/pruebas', 'Base aeróbica', Timer),
  nav('/plan-semanal', 'Plan semanal', ListChecks),
  // La tabla del equipo enseña nombres, ritmos y marcas de todos: el backend la
  // deja fuera del alcance del atleta con `require_coach`, y esto es su reflejo.
  nav('/equipo', 'Tabla del equipo', Table2, ['coach']),
  nav('/comparacion', 'Comparación', GitCompareArrows),
  nav('/simulador', 'Simulador', FlaskConical, ['coach']),
]

// Perfil no está en NAV_ITEMS: vive en el pie del rail, no en la lista de
// secciones. Pero la barra superior de móvil sí necesita saber rotularlo.
export const PROFILE_ITEM: NavItem = nav('/perfil', 'Perfil', UserRound)

/**
 * Si ese rol ve esa sección.
 *
 * `undefined` (la sesión no cargó) y `null` (la cuenta no está en ningún club)
 * no ven nada, por razones distintas: el primero porque todavía no se sabe, el
 * segundo porque no hay equipo cuyos datos enseñar. La única pantalla del
 * segundo es Perfil, que no está en esta lista — vive en el pie del rail.
 */
export function puedeVer(item: NavItem, role: string | null | undefined): boolean {
  if (role == null) return false
  if (!item.roles) return true
  return item.roles.includes(role as Role)
}

/** Las secciones del menú para ese rol. Vacío mientras la sesión carga. */
export function navItemsFor(role: string | null | undefined): NavItem[] {
  if (role == null) return []
  return NAV_ITEMS.filter((i) => puedeVer(i, role))
}

/**
 * La sección a la que corresponde una ruta, para rotular la barra superior.
 *
 * Devuelve `undefined` si la ruta no es ninguna sección conocida. Antes caía a
 * `NAV_ITEMS[0]`, así que una ruta oculta se rotulaba "Dashboard" y el usuario
 * veía un título que no correspondía a lo que tenía delante.
 */
export function activeNavItem(pathname: string): NavItem | undefined {
  return [...NAV_ITEMS, PROFILE_ITEM].find((i) => i.to === pathname)
}
