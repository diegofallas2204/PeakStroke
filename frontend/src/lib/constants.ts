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

export const DISTANCES = [50, 100, 200, 400, 800, 1500]

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
  sigmoid: '#8b5cf6',
  linear: '#34d399',
  exponential: '#fbbf24',
  logarithmic: '#f472b6',
}

export const ZONE_META: Record<string, { label: string; color: string }> = {
  R1: { label: 'Base aeróbica', color: '#34d399' },
  R2: { label: 'Umbral aeróbico', color: '#22d3ee' },
  MVO2: { label: 'VO2 máximo', color: '#a78bfa' },
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
  build: '#8b5cf6',
  peak: '#fbbf24',
  taper: '#34d399',
}

export const TEST_TYPE_LABEL: Record<string, string> = {
  T30: 'T-30',
  T15: 'T-15',
  CUSTOM: 'Personalizado',
  CSS: 'CSS 400/50',
  DIRECT: 'Directo',
}
