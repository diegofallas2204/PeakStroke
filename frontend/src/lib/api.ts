// Cliente HTTP tipado contra /api/v1 (proxy de Vite hacia FastAPI).
import type {
  AerobicPreview, AerobicTest, DashboardSummary, Plan, SimulationResult,
  Swimmer, TeamWeek, Week,
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
  swimmers: {
    list: (search?: string) =>
      get<Swimmer[]>(`/swimmers/${search ? `?search=${encodeURIComponent(search)}` : ''}`),
    create: (data: Partial<Swimmer>) => post<Swimmer>('/swimmers/', data),
    update: (id: number, data: Partial<Swimmer>) => put<Swimmer>(`/swimmers/${id}`, data),
    remove: (id: number) => del(`/swimmers/${id}`),
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
  },
}
