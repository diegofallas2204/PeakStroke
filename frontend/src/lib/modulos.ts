// Qué módulos trae esta build (2026-11-10).
//
// Cada sección del menú es un módulo, nombrado por su ruta: `inicio` (`/`),
// `macrociclos`, `atletas`, `pruebas`, `entrenamiento`, `plan-semanal`,
// `equipo` y `simulador`. Sirve para trabajar y publicar un módulo por
// separado: en la rama `modulo/inicio` la app solo enseña Inicio, y una
// versión de ese módulo es esa build. Ver `docs/MODULOS.md`.
//
// Lo elige `vite.config.ts` al arrancar (variable `VITE_MODULOS`, o el nombre
// de la rama) y llega aquí como `import.meta.env.VITE_MODULOS`: una lista
// separada por comas, o vacía para «todos».
//
// Apagar un módulo es **solo de la interfaz**: desaparece del menú, su ruta
// redirige y los enlaces que llevaban a él dejan de serlo. El backend es el
// mismo para todos y ya protege cada ruta por rol, así que esto no es una
// frontera de seguridad — es el alcance de una versión.
//
// Perfil, ajustes y la sesión no son módulos: son del sistema y siempre están.

/** El nombre de módulo de una ruta: su primer segmento, o `inicio` para `/`. */
export function moduloDe(ruta: string): string {
  const camino = ruta.split(/[?#]/)[0]
  const primero = camino.split('/').filter(Boolean)[0]
  return primero ?? 'inicio'
}

const SISTEMA = new Set(['perfil'])

/** `"inicio, atletas"` → `{inicio, atletas}`; vacío o `todos` → `null` (todos). */
export function parsearModulos(texto: string | undefined): Set<string> | null {
  const nombres = (texto ?? '').split(',').map((s) => s.trim().toLowerCase()).filter(Boolean)
  if (nombres.length === 0 || nombres.includes('todos')) return null
  return new Set(nombres)
}

/** Si la ruta es de un módulo encendido en `activos` (`null` = todos). */
export function rutaActiva(ruta: string, activos: Set<string> | null): boolean {
  const modulo = moduloDe(ruta)
  return activos === null || SISTEMA.has(modulo) || activos.has(modulo)
}

const ACTIVOS = parsearModulos(import.meta.env.VITE_MODULOS as string | undefined)

/** Los módulos de esta build, o `null` si vienen todos. */
export function modulosActivos(): Set<string> | null {
  return ACTIVOS
}

/** Si esa ruta (con o sin `?…`) es de un módulo de esta build. */
export function moduloActivo(ruta: string): boolean {
  return rutaActiva(ruta, ACTIVOS)
}

/**
 * El destino de un enlace si su módulo está en esta build; `undefined` si no.
 * Quien pinta un enlace a otra sección lo pasa por aquí y, sin destino, pinta
 * texto: un enlace a un módulo apagado rebotaría a otra pantalla sin explicar.
 */
export function enlace(a: string): string | undefined {
  return moduloActivo(a) ? a : undefined
}
