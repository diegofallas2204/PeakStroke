// El cliente de queries y su persistencia a disco.
//
// Vive aquí y no en `main.tsx` porque el conmutador de identidad necesita
// vaciarlo antes de recargar, e importarlo desde el punto de entrada crearía un
// ciclo (main → App → … → conmutador → main).
import { QueryClient } from '@tanstack/react-query'
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister'

// Queries efímeras y dependientes de parámetros (simulador, proyección anual,
// análisis de parciales): se computan en el motor y tienen muchas combinaciones.
// Se quedan SOLO en memoria —no se persisten— para no inflar localStorage.
export const EPHEMERAL_KEYS = new Set(['sim', 'season', 'analyze'])

// Queries atadas a QUIÉN está usando la app. Nunca se persisten: localStorage es
// del navegador, no de la cuenta, así que un cache persistido haría que la
// siguiente sesión en el mismo equipo viera la identidad y los miembros de la
// anterior durante 24 h. Cada carga de la página vuelve a preguntar al backend.
export const IDENTITY_KEYS = new Set([
  'session', 'auth-config', 'dev-identities', 'members', 'team', 'coach-athletes',
])

// Cache agresivo: los datos de dominio solo cambian por mutaciones de este mismo
// cliente, que invalidan su clave. Entre mutaciones se reusa el cache y se evitan
// llamadas redundantes al API (clave para muchos clientes simultáneos).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000,        // 5 min: navegar entre vistas no re-llama al API
      gcTime: 24 * 60 * 60_000,     // 24 h en cache (y persistido en disco)
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      retry: 1,
    },
  },
})

// Persistencia a localStorage: recargas y pestañas nuevas restauran el cache sin
// volver a pegarle al API. Se restaura solo lo no caducado (maxAge) y se invalida
// entero al subir `buster` (p. ej. tras cambiar el shape de una respuesta).
export const persister = createSyncStoragePersister({
  storage: window.localStorage,
  key: 'peakstroke-query-cache',
})

/**
 * Deja el cache vacío en memoria **y en disco**. La usa el conmutador de
 * identidad justo antes de recargar.
 *
 * `queryClient.clear()` a secas no basta, y el fallo cuesta verlo:
 * `createSyncStoragePersister` escribe con un throttle de 1 segundo, así que la
 * escritura pendiente —con los datos de la identidad anterior— llega DESPUÉS
 * del clear y sobrevive al reload. Con `staleTime` de 5 minutos esos datos se
 * quedan en pantalla mientras crees estar viendo a otra persona, que es
 * exactamente el error que el conmutador tiene que hacer imposible.
 */
export function limpiarCacheDeIdentidad() {
  persister.removeClient()
  queryClient.clear()
}
