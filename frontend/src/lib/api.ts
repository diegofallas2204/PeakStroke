// Cliente HTTP tipado contra /api/v1 (proxy de Vite hacia FastAPI).
import type {
  AerobicPreview, AerobicTest, AuthConfig, DashboardSummary, Member, MemberCreated,
  Plan, SeasonResult, SimulationResult, Swimmer, Team, TeamWeek, Week,
} from './types'

const BASE = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
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
  plans: {
    list: () => get<Plan[]>('/plans/'),
    getOne: (id: number) => get<Plan>(`/plans/${id}`),
    create: (data: unknown) => post<Plan>('/plans/', data),
    update: (id: number, data: unknown) => patch<Plan>(`/plans/${id}`, data),
    remove: (id: number) => del(`/plans/${id}`),
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
    analyze: (splits: number[], repDistance: number) =>
      post<AerobicPreview>('/aerobic-tests/analyze', { splits, rep_distance: repDistance }),
    previous: (testId: number) => get<AerobicTest | null>(`/aerobic-tests/${testId}/previous`),
    remove: (id: number) => del(`/aerobic-tests/${id}`),
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
