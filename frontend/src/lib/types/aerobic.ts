// Tests aeróbicos: lo que se apuntó, lo que se derivó y la pizarra que sale.

/** Cómo hay que leer los números que apuntó el entrenador. */
export type InputMode = 'rep' | 'clock'

export interface AerobicTest {
  id: number
  swimmer_id: number
  plan_id: number | null
  test_type: 'T30' | 'T15' | 'CUSTOM' | 'CSS' | 'DIRECT'
  test_date: string
  rep_count: number | null
  rep_distance: number | null
  /** Intervalo de salida en segundos. `null` en los tests que no lo registraron. */
  send_off: number | null
  input_mode: InputMode
  avg_per100: number
  std_dev: number | null
  trend: 'improving' | 'stable' | 'declining' | null
  css_ms: number | null
  notes: string | null
  splits: {
    rep_number: number
    split_time: number
    send_off_time: number | null
    arrival_time: number | null
  }[]
  per100_splits: number[]
  /** Derivados de la salida. Vacíos en los tests que no la tienen. */
  rest_per_rep: number[]
  avg_rest: number | null
  /** Descanso medio / trabajo medio. */
  work_rest_ratio: number | null
  /** Fracción del ciclo que es nado. */
  density: number | null
  /** Repeticiones que no llegaron antes de la salida siguiente (1..N). */
  missed_intervals: number[]
}

/** Una línea de pizarra: ritmo objetivo y cada cuánto sale la repetición. */
export interface TrainingInterval {
  zone: string
  label: string
  pace_100: number
  work: number
  rest: number
  interval: number
  rest_ratio: number
  /** La salida a la densidad que el atleta demostró en su test. */
  measured_interval: number | null
  denser_than_measured: boolean | null
}

export interface TrainingIntervals {
  test_id: number
  rep_distance: number
  /** `null` si el atleta no está inscrito en ningún macrociclo. */
  reference_pace: number | null
  reference_week: number | null
  event_label: string | null
  measured_ratio: number | null
  zones: TrainingInterval[]
}

export interface AerobicPreview {
  per100_splits: number[]
  avg_per100: number
  std_dev: number
  trend: string
  trend_slope: number
  /** Tiempos de nado ya despejados de la llegada, si venían como llegadas. */
  rep_times: number[]
  rest_per_rep: number[]
  avg_rest: number | null
  work_rest_ratio: number | null
  density: number | null
  missed_intervals: number[]
}
