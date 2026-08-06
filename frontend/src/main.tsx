import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient } from '@tanstack/react-query'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister'
import App from './App'
import { initTheme } from './hooks/useTheme'
import './index.css'

initTheme()

// Queries efímeras y dependientes de parámetros (simulador, proyección anual,
// análisis de parciales): se computan en el motor y tienen muchas combinaciones.
// Se quedan SOLO en memoria —no se persisten— para no inflar localStorage.
const EPHEMERAL_KEYS = new Set(['sim', 'season', 'analyze'])

// Queries atadas a QUIÉN está usando la app. Nunca se persisten: localStorage es
// del navegador, no de la cuenta, así que un cache persistido haría que la
// siguiente sesión en el mismo equipo viera la identidad y los miembros de la
// anterior durante 24 h. Cada carga de la página vuelve a preguntar al backend.
const IDENTITY_KEYS = new Set([
  'session', 'auth-config', 'members', 'team', 'coach-athletes',
])

// Cache agresivo: los datos de dominio solo cambian por mutaciones de este mismo
// cliente, que invalidan su clave. Entre mutaciones se reusa el cache y se evitan
// llamadas redundantes al API (clave para muchos clientes simultáneos).
const queryClient = new QueryClient({
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
const persister = createSyncStoragePersister({
  storage: window.localStorage,
  key: 'peakstroke-query-cache',
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: 24 * 60 * 60_000,   // 24 h
        // v2: se dejaron de persistir las queries de identidad. Subirlo tira el
        // cache viejo, que sí las traía dentro.
        buster: 'v2',
        dehydrateOptions: {
          shouldDehydrateQuery: (query) => {
            const key = String(query.queryKey[0])
            return query.state.status === 'success' &&
              !EPHEMERAL_KEYS.has(key) && !IDENTITY_KEYS.has(key)
          },
        },
      }}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </PersistQueryClientProvider>
  </StrictMode>,
)
