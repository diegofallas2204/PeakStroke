// Simulador: factibilidad de una meta, plan simulado y proyección de temporada.

import type { Zones } from './zones'

export interface Feasibility {
  status: 'ok' | 'warning' | 'aggressive'
  message: string
  tier: number
  improvement_total: number
  improvement_per_micro: number
  window_min: number | null
  window_max: number
  recommended_weeks: number | null
  extension_weeks: number | null
  realistic_ceiling: number
  safe_rate_per_week: number
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
  extension_weeks: SimWeek[]
  curves: Record<string, number[]>
}

export interface MacroProjection {
  n_mac: number
  start_time: number
  end_time: number
  improvement_s: number
  improvement_pct: number
}

export interface SeasonResult {
  level: string
  n_macros: number
  season_start: number
  season_end: number
  season_improvement_s: number
  season_improvement_pct: number
  annual_low_pct: number
  annual_high_pct: number
  verdict: string
  message: string
  macros: MacroProjection[]
}
