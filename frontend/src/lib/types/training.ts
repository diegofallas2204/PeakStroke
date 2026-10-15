// Entrenamiento: lo que el atleta nadó cada día (C7) y la carga que sale de
// ahí (C8, Banister). Espejo de `api/v1/sesiones/schemas.py` y
// `api/v1/carga/schemas.py`.

export interface TrainingSession {
  id: number
  swimmer_id: number
  /** 'YYYY-MM-DD'. */
  session_date: string
  distance_m: number
  /** Total, descansos incluidos: de la primera salida a la última llegada. */
  duration_s: number
  /** CR-10 de la sesión entera (Foster 2001). `null` si no se apuntó. */
  rpe: number | null
  notes: string | null
  /** Derivado, no se guarda: segundos por 100 m sobre la duración total. */
  pace_100m: number
}

export interface TrainingSessionInput {
  session_date: string
  distance_m: number
  duration_s: number
  rpe: number | null
  notes: string | null
}

export type LoadAlertLevel = 'advertencia' | 'peligro'
export type LoadAlertReason = 'tsb_bajo' | 'fatiga_sostenida' | 'rampa'

export interface LoadDay {
  date: string
  stss: number
  ctl: number
  atl: number
  tsb: number
  /** `null` sin alerta o durante el calentamiento. */
  alert: LoadAlertLevel | null
  reasons: LoadAlertReason[]
}

export interface TrainingLoad {
  swimmer_id: number
  desde: string
  hasta: string
  /** Primer día con carga. `null` sin sesiones con CSS. */
  history_start: string | null
  /** Menos de 14 días de historia: la curva se enseña, sin alertas. */
  warming_up: boolean
  /** Primer día con alertas; hasta ahí, la franja de calentamiento. */
  warmup_until: string | null
  /** Sesiones anteriores al primer test aeróbico: sin CSS no tienen carga. */
  sessions_without_css: number
  days: LoadDay[]
}

/** El estado de carga de un atleta un día: lo que pinta la tabla del equipo. */
export interface LoadSnapshot {
  date: string
  ctl: number
  atl: number
  tsb: number
  alert: LoadAlertLevel | null
  reasons: LoadAlertReason[]
  /** Menos de 14 días de historia ese día: sin alertas todavía. */
  warming_up: boolean
}
