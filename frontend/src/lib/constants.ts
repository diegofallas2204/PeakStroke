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

// Pruebas de natación válidas — misma regla que el backend (app/engine/events.py).
//   ≥600m → solo libre · 300–599m → libre/combinado · 100–299m → todos ·
//   <100m → libre/espalda/pecho/mariposa (no hay 50 combinado).
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

export const CURVES = [
  { value: 'sigmoid', label: 'Sigmoidal' },
  { value: 'linear', label: 'Lineal' },
  { value: 'exponential', label: 'Exponencial' },
  { value: 'logarithmic', label: 'Logarítmica' },
]

export const CURVE_LABEL: Record<string, string> = Object.fromEntries(
  CURVES.map((c) => [c.value, c.label]),
)

export const CURVE_COLORS: Record<string, string> = {
  sigmoid: 'var(--color-accent)',
  linear: 'var(--color-mint)',
  exponential: 'var(--color-amber)',
  logarithmic: 'var(--color-magenta)',
}

// Color distintivo por sección (ruta). Fuente única que comparten el sidebar
// (indicador activo) y cada página (barra de acento del encabezado). Tabla del
// equipo y Simulador se intercambiaron para separarlos de Plan semanal (rosa).
export const SECTION_ACCENT: Record<string, string> = {
  '/': '#3b82f6',              // Dashboard — azul
  '/macrociclos': '#22d3ee',   // Macrociclos — cian
  '/atletas': '#34d399',       // Atletas — esmeralda
  '/pruebas': '#fbbf24',       // Base aeróbica — ámbar
  '/plan-semanal': '#f472b6',  // Plan semanal — rosa
  '/equipo': '#fb923c',        // Tabla del equipo — naranja
  '/comparacion': '#a78bfa',   // Comparación — violeta
  '/simulador': '#fb7185',     // Simulador — coral
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

export const PHASE_COLORS: Record<string, string> = {
  base: '#22d3ee',
  build: '#3b82f6',
  peak: '#fbbf24',
  taper: '#34d399',
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
