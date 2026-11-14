// Test de lactato: espejo de `api/v1/tests/lactato_schemas.py`.
//
// Lo que se apunta (`LactateRepIn`) es poco; lo derivado vuelve en la respuesta
// y nunca se manda.

export type EstadoDeZona = 'debajo' | 'dentro' | 'encima'
export type ZonaDeLactato = 'R1' | 'R2' | 'MVO2' | 'RL' | 'V'

export interface LactateRepIn {
  swim_time: number
  lactate: number | null
  heart_rate: number | null
  effort: number | null
  stroke_counts: number[]
  segment_time: number | null
}

export interface LactateTestCreate {
  swimmer_id: number
  test_date: string
  target_zone: ZonaDeLactato
  rep_distance: number
  rest_type: 'pausa' | 'salida' | null
  rest_s: number | null
  proposed_min: number | null
  proposed_max: number | null
  reference_time: number | null
  counted_segment_m: number | null
  sample_site: 'dedo' | 'lobulo' | null
  analyzer: string | null
  sample_minute: number | null
  hr_method: 'banda' | 'palpacion' | 'optico' | null
  notes: string | null
  reps: LactateRepIn[]
}

export interface LactateRepOut extends LactateRepIn {
  rep_number: number
  speed: number
  pct_proposed: number | null
  pct_reference: number | null
  strokes_mean: number | null
  m_per_stroke: number | null
  cycle_rate: number | null
  cycle_rate_estimated: boolean
  stroke_index: number | null
  internal_drift_pct: number | null
  lactate_zone: EstadoDeZona | null
}

export interface LactateWarning {
  rep_number: number
  field: 'tiempo' | 'lactato' | 'fc'
  message: string
}

export interface LactateSummary {
  mean_time: number
  cv_pct: number
  slope: number
  speed: number
  pct_proposed: number | null
  diff_proposed: number | null
  pct_reference: number | null
  lactate_median: number | null
  lactate_min: number | null
  lactate_max: number | null
  lactate_zone: EstadoDeZona | null
  steady_state: boolean | null
  second_half_rise: number | null
  strokes_first: number | null
  strokes_last: number | null
  stroke_drift_pct: number | null
  stroke_index: number | null
}

export interface LactateAnalysis {
  zone_range: [number, number | null] | null
  reps: LactateRepOut[]
  summary: LactateSummary
  warnings: LactateWarning[]
}

export interface LactateTest extends LactateAnalysis, Omit<LactateTestCreate, 'reps'> {
  id: number
  mode: 'control' | 'escalonado'
  is_active: boolean
}
