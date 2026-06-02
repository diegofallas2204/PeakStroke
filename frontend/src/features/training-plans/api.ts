/**
 * training-plans/api.ts — Llamadas al backend para macrociclos.
 */
import { api } from '@/shared/lib/api'

// ── Tipos ─────────────────────────────────────────────────────────────────

export interface Zone {
  pace_100m: number
  r1: number; r2: number; mvo2: number; rl: number; v: number
}

export interface WeeklyPlan {
  id: number
  week_number: number
  week_date: string           // ISO date → mostrar como DD/MM en UI
  planned_km: number | null
  expected_time: number | null
  expected_time_recalc: number | null
  pace_100m: number | null
  zones: Zone | null
  real_time: number | null
  real_km: number | null
  disabled: boolean
  disable_reason: string | null
  phase_name: string | null
  feasibility: string | null
}

export interface AthleteEvent {
  id: number
  priority: number
  distance: number
  stroke: string
  current_time: number
  goal_time: number
  is_active: boolean
  improvement_seconds: number
  improvement_pct: number
  feasibility: string | null
  weekly_plans?: WeeklyPlan[]
}

export interface AthleteInMacrocycle {
  athlete_macrocycle_id: number
  swimmer_id: number
  aerobic_base: number | null
  aerobic_base_source: string | null
  events: AthleteEvent[]
}

export interface Phase {
  id: number; name: string; week_start: number; week_end: number; color: string | null
}

export interface Macrocycle {
  id: number
  name: string
  start_date: string
  end_date: string
  total_weeks: number
  microcycle_weeks: number
  sessions_per_week: number
  total_km: number
  progression_curve: string
  status: string
  notes: string | null
  phases: Phase[]
  athletes?: AthleteInMacrocycle[]
  swimmer_count?: number
}

export interface Swimmer {
  id: number
  name: string
  birth_date: string | null
  gender: string | null
  age: number | null
  specialty: string | null
}

export interface TeamRow {
  swimmer_id: number
  swimmer_name: string
  athlete_macrocycle_id: number
  event: AthleteEvent
  week: WeeklyPlan
}

// ── Macrociclos ───────────────────────────────────────────────────────────

export const macrocyclesApi = {
  list: () => api.get<Macrocycle[]>('/training-plans/').then(r => r.data),

  get: (id: number) => api.get<Macrocycle>(`/training-plans/${id}`).then(r => r.data),

  create: (data: {
    name: string; start_date: string; end_date: string
    total_weeks: 12 | 18; microcycle_weeks?: 4 | 5
    sessions_per_week?: number; total_km: number
    progression_curve?: string; notes?: string; phases?: Phase[]
  }) => api.post<Macrocycle>('/training-plans/', data).then(r => r.data),

  update: (id: number, data: Partial<Macrocycle>) =>
    api.patch<Macrocycle>(`/training-plans/${id}`, data).then(r => r.data),

  delete: (id: number) => api.delete(`/training-plans/${id}`),

  // Agregar atleta al macrociclo
  addAthlete: (macroId: number, data: {
    swimmer_id: number
    events: Array<{
      priority: 1 | 2 | 3; distance: number; stroke: string
      current_time: number; goal_time: number
    }>
    aerobic_base?: { value?: number; aerobic_test_id?: number } | null
  }) => api.post(`/training-plans/${macroId}/athletes`, data).then(r => r.data),

  // Tabla del equipo
  teamTable: (macroId: number, week: number) =>
    api.get<TeamRow[]>(`/training-plans/${macroId}/team?week=${week}`).then(r => r.data),

  // Actualizar semana
  updateWeek: (weekId: number, data: {
    real_time?: number | null; real_km?: number | null
    disabled?: boolean; disable_reason?: string | null
  }) => api.patch<WeeklyPlan>(`/training-plans/weeks/${weekId}`, data).then(r => r.data),
}

// ── Atletas ───────────────────────────────────────────────────────────────

export const swimmersApi = {
  list: () => api.get<Swimmer[]>('/training-plans/swimmers').then(r => r.data),

  create: (data: {
    name: string; birth_date?: string; gender?: string
    weight?: number; height?: number; specialty?: string
  }) => api.post<Swimmer>('/training-plans/swimmers', data).then(r => r.data),

  update: (id: number, data: Partial<Swimmer>) =>
    api.patch<Swimmer>(`/training-plans/swimmers/${id}`, data).then(r => r.data),
}

// ── Tests aeróbicos ───────────────────────────────────────────────────────

export const aerobicTestsApi = {
  list: (swimmerId: number) =>
    api.get(`/training-plans/aerobic-tests/${swimmerId}`).then(r => r.data),

  create: (data: {
    swimmer_id: number; macrocycle_id?: number
    test_type: 'T30' | 'T15'; test_date: string
    splits: number[]; notes?: string
  }) => api.post('/training-plans/aerobic-tests', data).then(r => r.data),
}
