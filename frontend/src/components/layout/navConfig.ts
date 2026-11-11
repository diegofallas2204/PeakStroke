// Catálogo único de secciones. Lo consumen el rail de escritorio, el drawer
// móvil, la barra superior (para rotular la sección activa) y las guardas de
// ruta de `App.tsx`.
//
// Que las rutas y los permisos vivan en la MISMA lista es deliberado: esconder
// una sección del menú no la hace inalcanzable —`/equipo` se puede teclear— así
// que si el filtro del menú y el de las rutas fueran dos listas, tarde o
// temprano dirían cosas distintas.
import {
  House, CalendarRange, Users, Timer, Table2,
  ListChecks, FlaskConical, UserRound, Activity, type LucideIcon,
} from 'lucide-react'
import { SECTION_ACCENT } from '../../lib/constants'
import { moduloActivo } from '../../lib/modulos'

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
  // «Inicio» y la casa (2026-11-10): antes «Dashboard», en inglés en una
  // interfaz en español. La ruta, los archivos y el API no cambian de nombre.
  nav('/', 'Inicio', House),
  nav('/macrociclos', 'Macrociclos', CalendarRange, ['coach']),
  nav('/atletas', 'Atletas', Users, ['coach']),
  nav('/pruebas', 'Base aeróbica', Timer),
  // De los dos roles, como Base aeróbica: el atleta apunta lo que nadó y el
  // entrenador lo ve (y lo corrige) en cada uno de sus atletas.
  nav('/entrenamiento', 'Entrenamiento', Activity),
  // Una sola entrada con tres vistas dentro (`?vista=`): Plan, Progresión y
  // Zonas. Comparación era una sección aparte que pedía los mismos datos con el
  // mismo selector; su contenido es hoy la vista Progresión, y `/comparacion`
  // redirige allí. Las vistas NO viven en esta lista: aquí solo hay secciones
  // —lo que el menú enseña y la guarda protege— y su catálogo es
  // `features/weekly/vistas.ts`.
  nav('/plan-semanal', 'Plan semanal', ListChecks),
  // La tabla del equipo enseña nombres, ritmos y marcas de todos: el backend la
  // deja fuera del alcance del atleta con `require_coach`, y esto es su reflejo.
  nav('/equipo', 'Tabla del equipo', Table2, ['coach']),
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
  // Un módulo que esta build no trae no se ve ni se alcanza (`lib/modulos.ts`).
  if (!moduloActivo(item.to)) return false
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
 * `NAV_ITEMS[0]`, así que una ruta oculta se rotulaba "Inicio" y el usuario
 * veía un título que no correspondía a lo que tenía delante.
 */
export function activeNavItem(pathname: string): NavItem | undefined {
  return seccionDe(pathname)
}

/**
 * La sección a la que pertenece una ruta: la suya exacta o la de su prefijo.
 * `/atletas/5` es de Atletas (2026-11-10): su color, su rótulo y **su guarda**.
 * Comparar la ruta exacta dejaba `/atletas/5` sin sección, y `RutaPorRol`
 * deja pasar lo que no reconoce: un atleta habría llegado a una página de
 * entrenador. `/` solo es Inicio exacta, o sería el prefijo de todo.
 */
export function seccionDe(pathname: string): NavItem | undefined {
  const todas = [...NAV_ITEMS, PROFILE_ITEM]
  return todas.find((i) => i.to === pathname)
    ?? todas.find((i) => i.to !== '/' && pathname.startsWith(`${i.to}/`))
}
