// Sesión activa: quién está usando la app y qué rol tiene.
// Con PEAKSTROKE_AUTH_ENABLED=false el backend responde el usuario de desarrollo,
// así que `data` siempre llega y no hace falta pantalla de login todavía.
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

export function useSession() {
  return useQuery({
    queryKey: ['session'],
    queryFn: () => api.auth.me(),
    // La identidad no cambia mientras dure la sesión; no tiene sentido refetchear.
    staleTime: Infinity,
    retry: false,
  })
}

export function useAuthConfig() {
  return useQuery({
    queryKey: ['auth-config'],
    queryFn: () => api.auth.config(),
    staleTime: Infinity,
    retry: false,
  })
}

/** true solo cuando la sesión ya cargó y es un entrenador. */
export function useIsCoach(): boolean {
  const { data } = useSession()
  return data?.role === 'coach'
}
