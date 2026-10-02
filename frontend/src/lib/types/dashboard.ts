// Resumen del equipo y la semana de equipo (`/dashboard/...`).

import type { PhaseInput } from './plans'
import type { LoadSnapshot } from './training'
import type { Zones } from './zones'

export interface TeamWeekPoint {
  week_number: number
  date_label: string
  expected_progress: number
  real_progress: number | null
  is_current: boolean
}

export interface AthleteStatusRow {
  athlete_plan_id: number
  swimmer_id: number
  event_id: number
  name: string
  specialty: string
  event_label: string
  expected_time: number
  recalc_time: number | null
  real_time: number | null
  status: 'ahead' | 'on_track' | 'behind' | 'pending' | null
  diff_seconds: number | null
  goal_time: number
  current_time: number
  progress_percent: number
}

export interface DashboardSummary {
  plan_id: number
  plan_name: string
  plan_status: string
  start_date: string
  total_weeks: number
  current_week: number | null
  current_phase: string | null
  athletes_total: number
  events_total: number
  ahead: number
  on_track: number
  behind: number
  pending: number
  compliance_percent: number
  avg_deviation_percent: number | null
  progression: TeamWeekPoint[]
  statuses: AthleteStatusRow[]
  phases: (PhaseInput & { is_current: boolean })[]
  competitions: {
    name: string
    week_number: number
    week_date: string
    days: number
    is_main: boolean
    weeks_away: number | null
  }[]
}

export interface TeamWeekRow {
  event_id: number
  /** Para enlazar con la curva del atleta en Entrenamiento. */
  swimmer_id: number | null
  week_id: number | null
  name: string
  specialty: string
  event_label: string
  expected_time: number | null
  pace_100m: number | null
  real_time: number | null
  status: string | null
  zones: Zones | null
  zone_km: Record<string, number> | null
  planned_km: number | null
  disabled: boolean
  /** Carga al cierre de la semana (sin pasar de hoy). `null` sin serie o semana futura. */
  load: LoadSnapshot | null
}

export interface TeamWeek {
  week_number: number
  date_label: string
  phase: string | null
  rows: TeamWeekRow[]
}
