// Catálogos compartidos de dominio y de estilo visual.

export const STROKES = [
  { value: 'libre', label: 'Libre' },
  { value: 'espalda', label: 'Espalda' },
  { value: 'pecho', label: 'Pecho' },
  { value: 'mariposa', label: 'Mariposa' },
  { value: 'combinado', label: 'Combinado' },
]

export const STROKE_LABEL: Record<string, string> = Object.fromEntries(
  STROKES.map((s) => [s.value, s.label]),
)

export const SPECIALTIES = [
  { value: 'velocidad', label: 'Velocidad' },
  { value: 'medio_fondo', label: 'Medio fondo' },
  { value: 'fondo', label: 'Fondo' },
  { value: 'aguas_abiertas', label: 'Aguas abiertas' },
]

export const SPECIALTY_LABEL: Record<string, string> = Object.fromEntries(
  SPECIALTIES.map((s) => [s.value, s.label]),
)

// Especialidad sugerida por la distancia de la prueba (espejo de
// domain.profile_for_event): velocidad ≤100 · medio fondo 200-400 · fondo ≥800.
// El simulador la autoselecciona desde el diagnóstico; el coach puede cambiarla.
export function specialtyForDistance(distance: number): string {
  if (distance <= 100) return 'velocidad'
  if (distance <= 400) return 'medio_fondo'
  return 'fondo'
}

export const DISTANCES = [50, 100, 200, 400, 800, 1500]

// Pruebas de natación válidas — misma regla que el backend, donde es una
// invariante del constructor de `Prueba` (app/dominio/valores/prueba.py).
//   ≥600m → solo libre · 300–599m → libre/combinado · 100–299m → todos ·
//   <100m → libre/espalda/pecho/mariposa (no hay 50 combinado).
// Esto solo filtra los desplegables: quien RECHAZA es el backend, con un 422.
// Si cambia la regla, hay que tocar los dos sitios.
export function strokesForDistance(distance: number): string[] {
  if (distance >= 600) return ['libre']
  if (distance >= 300) return ['libre', 'combinado']
  const base = ['libre', 'espalda', 'pecho', 'mariposa']
  if (distance >= 100) base.push('combinado')
  return base
}

// Opciones de estilo (value/label) válidas para una distancia, en el orden de STROKES.
export function strokeOptionsForDistance(distance: number) {
  const allowed = strokesForDistance(distance)
  return STROKES.filter((s) => allowed.includes(s.value))
}

export function isValidEvent(distance: number, stroke: string): boolean {
  return strokesForDistance(distance).includes(stroke)
}

// Devuelve el estilo si es válido para la distancia; si no, el primero válido (libre).
export function coerceStroke(distance: number, stroke: string): string {
  return isValidEvent(distance, stroke) ? stroke : strokesForDistance(distance)[0]
}

export const POOLS = [
  { value: '50', label: '50 m (piscina larga)' },
  { value: '25', label: '25 m (piscina corta)' },
]

export const POOL_LABEL: Record<string, string> = Object.fromEntries(
  POOLS.map((p) => [p.value, p.label]),
)

// "science" = curva científica por defecto (distribución F_FASE del motor de
// dominio, respaldada por la literatura). Las demás solo comparan escenarios.
export const CURVES = [
  { value: 'science', label: 'Científica (F_FASE)' },
  { value: 'sigmoid', label: 'Sigmoidal' },
  { value: 'linear', label: 'Lineal' },
  { value: 'exponential', label: 'Exponencial' },
  { value: 'logarithmic', label: 'Logarítmica' },
]

export const CURVE_LABEL: Record<string, string> = Object.fromEntries(
  CURVES.map((c) => [c.value, c.label]),
)

export const CURVE_COLORS: Record<string, string> = {
  science: 'var(--color-accent)',
  sigmoid: 'var(--color-magenta)',
  linear: 'var(--color-mint)',
  exponential: 'var(--color-amber)',
  logarithmic: 'var(--color-text-faint)',
}

// Color distintivo por sección (ruta). Fuente única que comparten el sidebar
// (indicador activo) y cada página (barra de acento del encabezado).
//
// UN color por RUTA, no por vista: el riel, la barra superior de móvil y la
// cabecera lo leen del mismo pathname, así que el color contesta "dónde estoy".
// Las tres vistas de Plan semanal comparten el suyo — si cambiara con la
// pestaña, el riel y la página dirían sitios distintos a la vez.
//
// El violeta #a78bfa quedó LIBRE al fusionar Comparación dentro de Plan semanal
// (decisión R9, 2026-08-16): la sección superviviente CONSERVA su rosa. Absorbió
// algo, no se convirtió en otra cosa —misma ruta, mismo nombre, y la pestaña
// "Plan" es la página de siempre—, así que su color persiste. Liberar el rosa
// habría creado una trampa: reaparecería en otra sección contradiciendo a quien
// ya lo tenía asociado a Plan semanal. El violeta no la crea, porque ya no
// señala nada que se pueda volver a encontrar.
//
// OJO al reasignar: el coral de Simulador y este rosa son casi indistinguibles
// en tema oscuro. Por eso Tabla del equipo y Simulador tienen los colores
// intercambiados —el coral está lejos de Plan semanal en el riel, no pegado a
// él—. Ese intercambio NO se puede deshacer mientras esta sección sea rosa.
export const SECTION_ACCENT: Record<string, string> = {
  '/': '#3b82f6',              // Dashboard — azul
  '/macrociclos': '#22d3ee',   // Macrociclos — cian
  '/atletas': '#34d399',       // Atletas — esmeralda
  '/pruebas': '#fbbf24',       // Base aeróbica — ámbar
  '/plan-semanal': '#f472b6',  // Plan semanal — rosa
  '/equipo': '#fb923c',        // Tabla del equipo — naranja
  '/simulador': '#fb7185',     // Simulador — coral
  '/perfil': '#818cf8',        // Perfil — índigo
}

// Rol dentro del equipo (valor crudo en BD -> etiqueta + color).
export const ROLE_META: Record<string, { label: string; color: string }> = {
  coach: { label: 'Entrenador', color: '#818cf8' },
  athlete: { label: 'Atleta', color: '#22d3ee' },
}

// El dueño del equipo no es un rol aparte: es el entrenador que además lo posee.
// De cara al usuario eso se llama entrenador en jefe.
export const HEAD_COACH = { label: 'Entrenador en jefe', color: '#fbbf24' }

// Cuenta que existe en el sistema y todavía no está en ningún club. No es un
// rol: es la ausencia de uno, y por eso no vive en ROLE_META.
export const NO_TEAM = { label: 'Sin equipo', color: '#8b93b8' }

export function roleMeta(role: string | null | undefined, isOwner = false) {
  // `null` (sin club) y `undefined` (la sesión aún no cargó) se pintan igual a
  // propósito: en los dos casos lo honesto es no afirmar un rol. La diferencia
  // la usan la navegación y las rutas, no la etiqueta.
  if (!role) return NO_TEAM
  if (isOwner && role === 'coach') return HEAD_COACH
  return ROLE_META[role] ?? ROLE_META.athlete
}

export const ZONE_META: Record<string, { label: string; color: string }> = {
  R1: { label: 'Base aeróbica', color: '#34d399' },
  R2: { label: 'Umbral aeróbico', color: '#22d3ee' },
  MVO2: { label: 'VO2 máximo', color: '#60a5fa' },
  RL: { label: 'Res. lactato', color: '#fbbf24' },
  V: { label: 'Velocidad', color: '#fb7185' },
}

export const ZONE_ORDER = ['R1', 'R2', 'MVO2', 'RL', 'V']

export const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  ahead: { label: 'Adelantado', color: '#34d399', bg: 'rgba(52,211,153,.12)' },
  on_track: { label: 'En plan', color: '#22d3ee', bg: 'rgba(34,211,238,.12)' },
  behind: { label: 'Atrasado', color: '#fb7185', bg: 'rgba(251,113,133,.12)' },
  pending: { label: 'Sin datos', color: '#8b93b8', bg: 'rgba(139,147,184,.12)' },
}

// Estado de ciclo de vida del macrociclo (valor crudo en BD -> etiqueta + color).
export const PLAN_STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  active: { label: 'Activo', color: '#34d399', bg: 'rgba(52,211,153,.12)' },
  finished: { label: 'Completado', color: '#60a5fa', bg: 'rgba(96,165,250,.12)' },
  draft: { label: 'Inactivo', color: '#8b93b8', bg: 'rgba(139,147,184,.12)' },
  suspended: { label: 'Suspendido', color: '#fb7185', bg: 'rgba(251,113,133,.12)' },
}

export const TEST_TYPE_LABEL: Record<string, string> = {
  T30: 'T-30',
  T15: 'T-15',
  CUSTOM: 'Personalizado',
  CSS: 'CSS 400/50',
  DIRECT: 'Directo',
}
