import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import App from './App'
import { initTheme } from './hooks/useTheme'
import { EPHEMERAL_KEYS, IDENTITY_KEYS, persister, queryClient } from './lib/queryClient'
import './index.css'

initTheme()

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
