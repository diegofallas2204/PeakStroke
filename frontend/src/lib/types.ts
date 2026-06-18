// Tipos espejo de los schemas Pydantic del backend.

export interface Swimmer {
  id: number
  name: string
  birth_date: string | null
  gender: string | null
  specialty: string
  main_stroke: string
  weight_kg: number | null
  height_cm: number | null
  notes: string | null
  created_at: string
  age: number | null
}

export interface PhaseInput {
  name: string
  type: string
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
  progression_curve: string
  main_event: string | null
  notes: string | null
  status: string
  effective_status: string
  phases: Phase[]
  competitions: Competition[]
  athletes: AthletePlan[]
  current_week: number | null
}

export type ZoneRange = { min: number; mid: number; max: number } | null
export type Zones = Record<string, ZoneRange>

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

export interface AerobicTest {
  id: number
  swimmer_id: number
  plan_id: number | null
  test_type: 'T30' | 'T15' | 'CUSTOM' | 'CSS' | 'DIRECT'
  test_date: string
  rep_count: number | null
  rep_distance: number | null
  avg_per100: number
  std_dev: number | null
  trend: 'improving' | 'stable' | 'declining' | null
  css_ms: number | null
  notes: string | null
  splits: { rep_number: number; split_time: number }[]
  per100_splits: number[]
}

export interface Feasibility {
  status: 'ok' | 'warning' | 'aggressive'
  message: string
  tier: number
  improvement_total: number
  improvement_per_micro: number
  window_min: number | null
  window_max: number
  recommended_weeks: number | null
  detail: Record<string, unknown>
}

export interface SimWeek {
  week_number: number
  date_label: string
  expected_time: number
  pace_100m: number
  planned_km: number
  phase: string
  improvement_vs_prev: number
  cumulative_improvement: number
  zones: Zones
  zone_km: Record<string, number>
}

export interface SimulationResult {
  feasibility: Feasibility
  weeks: SimWeek[]
  curves: Record<string, number[]>
}

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
}

export interface TeamWeek {
  week_number: number
  date_label: string
  phase: string | null
  rows: TeamWeekRow[]
}

export interface AerobicPreview {
  per100_splits: number[]
  avg_per100: number
  std_dev: number
  trend: string
  trend_slope: number
}
