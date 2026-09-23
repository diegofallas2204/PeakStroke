// El macrociclo: fases, competencias, atletas inscritos y sus semanas.

import type { Zones } from './zones'

/** Una ficha que hoy puede entrar en un macrociclo. */
export interface AssignableAthlete {
  id: number
  name: string
  age: number | null
  specialty: string
  main_stroke: string
}

/**
 * Las cinco fases del macrociclo, por su clave de dominio (`Fase` en el backend).
 * El nombre que se enseña es aparte (`name`): el entrenador lo elige.
 * `backend/tests/test_fases_del_macro.py` lee esta línea y falla si se separan.
 */
export type ClaveDeFase = 'base_general' | 'base_especifica' | 'umbral_css' | 'pre_competitivo' | 'taper'

export interface PhaseInput {
  name: string
  type: ClaveDeFase
  week_start: number
  week_end: number
  color: string
}

export interface Phase extends PhaseInput {
  id: number
  sort: number
}

export interface Competition {
  id: number
  name: string
  week_number: number
  days: number
  is_main: boolean
}

export interface AthleteEvent {
  id: number
  priority: number
  distance: number
  stroke: string
  current_time: number
  goal_time: number
}

export interface AthletePlan {
  id: number
  swimmer_id: number
  swimmer_name: string
  specialty: string
  aerobic_base: number | null
  aerobic_base_source: string | null
  events: AthleteEvent[]
}

export interface Plan {
  id: number
  name: string
  start_date: string
  total_weeks: number
  weeks_per_micro: number
  total_km: number
  pool: string
  n_mac: number
  main_event: string | null
  notes: string | null
  status: string
  effective_status: string
  phases: Phase[]
  competitions: Competition[]
  athletes: AthletePlan[]
  current_week: number | null
}

export interface Week {
  id: number
  week_number: number
  week_date: string
  date_label: string
  planned_km: number
  expected_time: number
  recalc_time: number | null
  pace_100m: number
  zones: Zones
  zone_km: Record<string, number>
  real_time: number | null
  status: 'ahead' | 'on_track' | 'behind' | null
  diff_seconds: number | null
  diff_percent: number | null
  phase: string
  disabled: boolean
  disable_reason: string | null
  is_competition: boolean
}
