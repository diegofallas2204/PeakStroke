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

/**
 * true solo cuando la sesión ya cargó y además es el dueño del equipo.
 *
 * Entrenador en jefe = entrenador que además es `teams.owner_id`; no es un
 * tercer rol. Este hook existe para que ese cálculo no se repita a mano por la
 * UI, que es como se acaba con cuatro versiones ligeramente distintas.
 */
export function useIsOwner(): boolean {
  const { data } = useSession()
  return data?.role === 'coach' && data?.is_owner === true
}

/** true solo cuando la sesión ya cargó y es un atleta. */
export function useIsAthlete(): boolean {
  const { data } = useSession()
  return data?.role === 'athlete'
}

/**
 * El rol efectivo. Tres valores, y los tres significan cosas distintas:
 *
 *   `undefined` — la sesión todavía no cargó. **No es "sin permiso"**: quien
 *                 filtre navegación o rutas debe esperar, o el rail parpadea
 *                 vacío y las rutas rebotan.
 *   `null`      — ya se sabe quién es, y no pertenece a ningún club. Solo tiene
 *                 su perfil, donde están sus solicitudes de ingreso.
 *   `'coach'` / `'athlete'` — rol dentro de su club.
 *
 * Juntar los dos primeros en un solo valor haría que la pantalla de quien
 * espera invitación fuera un spinner eterno.
 */
export function useRole(): string | null | undefined {
  const { data } = useSession()
  return data?.role
}

/** true cuando la sesión ya cargó y esa cuenta no está en ningún club. */
export function useSinEquipo(): boolean {
  const { data } = useSession()
  return data != null && data.role == null
}
