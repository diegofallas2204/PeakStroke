// Cliente HTTP tipado contra /api/v1 (proxy de Vite hacia FastAPI).
import { getDevBypass, getDevIdentity } from '../hooks/useDevIdentity'
import type {
  AerobicPreview, AerobicTest, AssignableAthlete, AuthConfig, DashboardSummary,
  DevIdentity, InputMode, InviteResult, JoinRequest, LinkCode, Member,
  MemberCreated, PhaseInput, Plan, SeasonResult, SimulationResult, Swimmer, Team, TeamWeek,
  TrainingIntervals, TrainingLoad, TrainingSession, TrainingSessionInput, Week,
} from './types'

const BASE = '/api/v1'

// Nombres fijados aquí y no leídos de `/auth/config` a propósito: la primera
// petición del arranque ES la de config, así que esperarla para saber cómo
// mandar cabeceras sería circular. El backend expone los nombres para que el
// cliente pueda comprobar que coinciden, no para descubrirlos.
const DEV_USER_HEADER = 'X-PeakStroke-Dev-User'
const DEV_BYPASS_HEADER = 'X-PeakStroke-Dev-Bypass'

/** Las cabeceras del conmutador, si hay algo que decir. */
function devHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  const identity = getDevIdentity()
  if (identity) headers[DEV_USER_HEADER] = identity
  if (getDevBypass()) headers[DEV_BYPASS_HEADER] = 'true'
  return headers
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    // Las cabeceras se MEZCLAN, no se reemplazan. Antes `...options` iba después
    // y un llamador con `headers` propios tiraba el Content-Type en silencio.
    // Hoy no hay ninguno, pero el conmutador añade las suyas aquí mismo y el
    // fallo habría sido un 422 sin explicación.
    headers: {
      'Content-Type': 'application/json',
      ...devHeaders(),
      ...(options?.headers as Record<string, string> | undefined),
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* respuesta sin cuerpo JSON */ }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

const get = <T,>(path: string) => request<T>(path)
const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })
const patch = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
const put = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
const del = (path: string) => request<void>(path, { method: 'DELETE' })

export const api = {
  auth: {
    // Con la autenticación apagada devuelve el usuario de desarrollo, así que
    // siempre hay sesión: el frontend no necesita pantalla de login todavía.
    me: () => get<Member>('/auth/me'),
    config: () => get<AuthConfig>('/auth/config'),
    // Las cuentas que el conmutador puede suplantar. 404 con el login real
    // encendido: allí este endpoint no existe.
    devIdentities: () => get<DevIdentity[]>('/auth/dev-identities'),
    members: () => get<Member[]>('/auth/members'),
    createMember: (data: unknown) => post<MemberCreated>('/auth/members', data),
    updateMember: (id: number, data: unknown) => patch<Member>(`/auth/members/${id}`, data),
    changePassword: (currentPassword: string, newPassword: string) =>
      post<void>('/auth/me/password', {
        current_password: currentPassword, new_password: newPassword,
      }),
  },
  teams: {
    mine: () => get<Team>('/teams/mine'),
    rename: (name: string) => patch<Team>('/teams/mine', { name }),
    transfer: (newOwnerId: number) =>
      post<Team>('/teams/mine/transfer', { new_owner_id: newOwnerId }),
    coachAthletes: (coachId: number) =>
      get<number[]>(`/teams/mine/coaches/${coachId}/athletes`),
    setCoachAthletes: (coachId: number, swimmerIds: number[]) =>
      put<number[]>(`/teams/mine/coaches/${coachId}/athletes`, {
        coach_id: coachId, swimmer_ids: swimmerIds,
      }),
  },
  swimmers: {
    list: (search?: string, includeInactive = false) => {
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (includeInactive) params.set('include_inactive', 'true')
      const qs = params.toString()
      return get<Swimmer[]>(`/swimmers/${qs ? `?${qs}` : ''}`)
    },
    getOne: (id: number) => get<Swimmer>(`/swimmers/${id}`),
    create: (data: Partial<Swimmer>) => post<Swimmer>('/swimmers/', data),
    update: (id: number, data: Partial<Swimmer>) => put<Swimmer>(`/swimmers/${id}`, data),
    // No borra: da de baja. Devuelve el atleta con is_active en false.
    deactivate: (id: number) => request<Swimmer>(`/swimmers/${id}`, { method: 'DELETE' }),
    reactivate: (id: number) => post<Swimmer>(`/swimmers/${id}/reactivate`, {}),
  },
  // Ligar una cuenta a una ficha. Lo emite el entrenador, lo canjea la persona:
  // hasta que no ocurren las dos cosas no hay relación.
  linkCodes: {
    list: () => get<LinkCode[]>('/link-codes/'),
    issue: (swimmerId: number) => post<LinkCode>('/link-codes/', { swimmer_id: swimmerId }),
    /** Alta de un atleta al equipo por su correo: ficha + cuenta + código. */
    invite: (data: unknown) => post<InviteResult>('/link-codes/invite', data),
    /** Mis solicitudes de ingreso pendientes. Nunca traen el código. */
    mine: () => get<JoinRequest[]>('/link-codes/mine'),
    revoke: (id: number) => del(`/link-codes/${id}`),
    redeem: (code: string) =>
      post<{ swimmer_id: number; swimmer_name: string; team_id: number; team_name: string }>(
        '/link-codes/redeem', { code },
      ),
  },
  plans: {
    list: () => get<Plan[]>('/plans/'),
    getOne: (id: number) => get<Plan>(`/plans/${id}`),
    create: (data: unknown) => post<Plan>('/plans/', data),
    // Las fases con las que nace un macro de N semanas. Las decide el motor: son
    // la forma de la curva científica, y la copia que tenía el asistente ya se
    // había separado del backend en los colores.
    defaultPhases: (weeks: number) => get<PhaseInput[]>(`/plans/default-phases?weeks=${weeks}`),
    update: (id: number, data: unknown) => patch<Plan>(`/plans/${id}`, data),
    remove: (id: number) => del(`/plans/${id}`),
    // Los que HOY pueden entrar en ese macrociclo: ni los que ya están dentro
    // ni los comprometidos con otro que sigue vivo. El POST aplica la misma
    // regla, así que la lista no es una restricción de la interfaz.
    assignableAthletes: (planId: number) =>
      get<AssignableAthlete[]>(`/plans/${planId}/assignable-athletes`),
    addAthlete: (planId: number, data: unknown) => post<Plan>(`/plans/${planId}/athletes`, data),
    removeAthlete: (planId: number, athletePlanId: number) =>
      del(`/plans/${planId}/athletes/${athletePlanId}`),
    eventWeeks: (eventId: number) => get<Week[]>(`/plans/events/${eventId}/weeks`),
    updateWeek: (weekId: number, data: unknown) => patch<Week[]>(`/plans/weeks/${weekId}`, data),
  },
  aerobic: {
    list: (swimmerId?: number) =>
      get<AerobicTest[]>(`/aerobic-tests/${swimmerId ? `?swimmer_id=${swimmerId}` : ''}`),
    create: (data: unknown) => post<AerobicTest>('/aerobic-tests/', data),
    analyze: (
      splits: number[], repDistance: number,
      sendOff?: number | null, inputMode: InputMode = 'rep',
    ) =>
      post<AerobicPreview>('/aerobic-tests/analyze', {
        splits, rep_distance: repDistance,
        send_off: sendOff ?? null, input_mode: inputMode,
      }),
    previous: (testId: number) => get<AerobicTest | null>(`/aerobic-tests/${testId}/previous`),
    /** Ritmo + salida por zona para repeticiones de `repDistance` metros. */
    trainingIntervals: (testId: number, repDistance = 100) =>
      get<TrainingIntervals>(
        `/aerobic-tests/${testId}/training-intervals?rep_distance=${repDistance}`,
      ),
    remove: (id: number) => del(`/aerobic-tests/${id}`),
  },
  // Lo que el atleta nadó cada día. El atleta apunta lo suyo y el entrenador lo
  // de sus atletas; lo ajeno es 404. El borrado es REAL (excepción a «nada se
  // borra»): la sesión es un registro que su dueño corrige.
  sessions: {
    list: (swimmerId: number, desde?: string, hasta?: string) => {
      const params = new URLSearchParams({ swimmer_id: String(swimmerId) })
      if (desde) params.set('desde', desde)
      if (hasta) params.set('hasta', hasta)
      return get<TrainingSession[]>(`/sessions/?${params}`)
    },
    create: (swimmerId: number, data: TrainingSessionInput) =>
      post<TrainingSession>('/sessions/', { swimmer_id: swimmerId, ...data }),
    update: (id: number, data: Partial<TrainingSessionInput>) =>
      patch<TrainingSession>(`/sessions/${id}`, data),
    remove: (id: number) => del(`/sessions/${id}`),
  },
  // CTL / ATL / TSB por día. Derivado: aquí no se escribe nada.
  trainingLoad: {
    get: (swimmerId: number, desde?: string, hasta?: string) => {
      const params = new URLSearchParams()
      if (desde) params.set('desde', desde)
      if (hasta) params.set('hasta', hasta)
      const qs = params.toString()
      return get<TrainingLoad>(`/training-load/${swimmerId}${qs ? `?${qs}` : ''}`)
    },
  },
  dashboard: {
    summary: (planId?: number) =>
      get<DashboardSummary>(`/dashboard/summary${planId ? `?plan_id=${planId}` : ''}`),
    teamWeek: (planId?: number, week?: number) => {
      const params = new URLSearchParams()
      if (planId) params.set('plan_id', String(planId))
      if (week) params.set('week', String(week))
      const qs = params.toString()
      return get<TeamWeek>(`/dashboard/team-week${qs ? `?${qs}` : ''}`)
    },
  },
  simulator: {
    run: (data: unknown) => post<SimulationResult>('/simulator/run', data),
    season: (data: unknown) => post<SeasonResult>('/simulator/season', data),
  },
}
