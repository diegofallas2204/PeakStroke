/**
 * useMacrocycles.ts — React Query hooks para macrociclos.
 * Todos los componentes consumen datos desde aquí, nunca llaman a la API directamente.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { macrocyclesApi, swimmersApi, type Macrocycle } from '../api'

const KEYS = {
  macrocycles: ['macrocycles'] as const,
  macrocycle: (id: number) => ['macrocycles', id] as const,
  team: (macroId: number, week: number) => ['macrocycles', macroId, 'team', week] as const,
  swimmers: ['swimmers'] as const,
}

// ── Macrociclos ───────────────────────────────────────────────────────────

export function useMacrocycles() {
  return useQuery({ queryKey: KEYS.macrocycles, queryFn: macrocyclesApi.list })
}

export function useMacrocycle(id: number) {
  return useQuery({
    queryKey: KEYS.macrocycle(id),
    queryFn: () => macrocyclesApi.get(id),
    enabled: !!id,
  })
}

export function useCreateMacrocycle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: macrocyclesApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.macrocycles }),
  })
}

export function useDeleteMacrocycle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: macrocyclesApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.macrocycles }),
  })
}

// ── Atletas en macrociclo ─────────────────────────────────────────────────

export function useAddAthlete(macroId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Parameters<typeof macrocyclesApi.addAthlete>[1]) =>
      macrocyclesApi.addAthlete(macroId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.macrocycle(macroId) }),
  })
}

// ── Tabla del equipo ──────────────────────────────────────────────────────

export function useTeamTable(macroId: number, week: number) {
  return useQuery({
    queryKey: KEYS.team(macroId, week),
    queryFn: () => macrocyclesApi.teamTable(macroId, week),
    enabled: !!macroId,
  })
}

// ── Actualizar semana ─────────────────────────────────────────────────────

export function useUpdateWeek(macroId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ weekId, data }: {
      weekId: number
      data: Parameters<typeof macrocyclesApi.updateWeek>[1]
    }) => macrocyclesApi.updateWeek(weekId, data),
    onSuccess: (_, { data }) => {
      // Invalidar tabla del equipo y detalle del macro
      qc.invalidateQueries({ queryKey: KEYS.macrocycle(macroId) })
    },
  })
}

// ── Atletas (CRUD) ────────────────────────────────────────────────────────

export function useSwimmers() {
  return useQuery({ queryKey: KEYS.swimmers, queryFn: swimmersApi.list })
}

export function useCreateSwimmer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: swimmersApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.swimmers }),
  })
}
