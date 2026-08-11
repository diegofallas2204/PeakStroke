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
  user_id: number | null
  /** Email de la cuenta ligada, si la ficha ya tiene una. */
  user_email: string | null
  /** Los atletas se dan de baja, no se borran. */
  is_active: boolean
}

/**
 * Código de vinculación vivo: emitido, sin canjear y sin caducar.
 *
 * No viaja dentro de `Swimmer` a propósito — el backend lo sirve aparte
 * (`GET /link-codes/`) para no tener la definición de "código vivo" en dos
 * módulos. Quien pinte el estado de una ficha cruza las dos listas por
 * `swimmer_id`.
 */
export interface LinkCode {
  id: number
  swimmer_id: number
  swimmer_name: string
  /** A quién va dirigido, si se emitió desde el correo. */
  invited_email: string | null
  /** Ya formateado con guion: `ABCD-2345`. */
  code: string
  expires_at: string
  created_at: string
}

/** Alta de un atleta al equipo por su correo: ficha + cuenta + código. */
export interface InviteResult {
  link_code: LinkCode
  account_created: boolean
  /** Solo si la cuenta se acaba de crear. No se puede volver a consultar. */
  temporary_password: string | null
}

/**
 * Una solicitud de ingreso, vista desde el lado del atleta.
 *
 * **Sin el código, a propósito**: teclearlo es la prueba de que quien acepta es
 * quien el entrenador invitó. Enseñarlo aquí lo dejaría en un botón.
 */
export interface JoinRequest {
  team_name: string
  swimmer_name: string
  invited_by: string | null
  expires_at: string
  created_at: string
}

/** Una ficha que hoy puede entrar en un macrociclo. */
export interface AssignableAthlete {
  id: number
  name: string
  age: number | null
  specialty: string
  main_stroke: string
}

export type Role = 'coach' | 'athlete'

/** Un usuario junto con el nadador al que está ligado, si lo está. */
export interface Member {
  id: number
  email: string
  name: string
  /**
   * `null` = la cuenta existe pero no está en ningún club todavía.
   *
   * Es el estado de quien espera invitación, y no es lo mismo que `undefined`
   * («la sesión aún no cargó»): con `null` ya se sabe quién es, y lo que se
   * sabe es que solo puede ver su perfil.
   */
  role: Role | null
  is_active: boolean
  created_at: string
  last_login_at: string | null
  team_id: number | null
  team_name: string | null
  /** Entrenador en jefe = entrenador que además es dueño del equipo. */
  is_owner: boolean
  swimmer_id: number | null
  swimmer_name: string | null
}

export interface Team {
  id: number
  name: string
  owner_id: number | null
  owner_name: string | null
  is_owner: boolean
  coaches: number
  athletes: number
  swimmers: number
}

export interface MemberCreated {
  member: Member
  /** Solo si la generó el backend; no se puede volver a consultar. */
  temporary_password: string | null
}

export interface AuthConfig {
  auth_enabled: boolean
  /** Si existe el conmutador de desarrollo. False ⇒ no dibujar la barra. */
  dev_identities_enabled: boolean
  /** Si ESTA petición viajó en modo desarrollador (sale de la cabecera que se mandó). */
  dev_bypass_active: boolean
  /** Nombres de las cabeceras, para no llevarlos a fuego en el cliente. */
  dev_user_header: string | null
  dev_bypass_header: string | null
}

/** Una cuenta que el conmutador de desarrollo puede suplantar. */
export interface DevIdentity {
  email: string
  name: string
  /** `null` = cuenta del pool, sin club todavía. */
  role: string | null
  is_owner: boolean
  swimmer_name: string | null
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

/**
 * El objetivo de una zona: a qué ritmo y cada cuánto sale la repetición.
 *
 * `mid` es el objetivo científico; `min`/`max` son ±1% de tolerancia de
 * visualización. `send_off` es el intervalo ya cuadrado al reloj de pared (5 s)
 * y `rest` el descanso real que queda dentro de ese ciclo. Las dos mitades
 * viajan juntas porque una prescripción son las dos: el ritmo solo no se puede
 * escribir en la pizarra.
 */
export type ZoneRange = {
  min: number
  mid: number
  max: number
  send_off: number
  rest: number
  rep_distance: number
} | null
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
  /** Tiempos de nado ya despejados de la llegada, si venían como llegadas. */
  rep_times: number[]
  rest_per_rep: number[]
  avg_rest: number | null
  work_rest_ratio: number | null
  density: number | null
  missed_intervals: number[]
}
