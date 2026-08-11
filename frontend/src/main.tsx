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
        // v3 (2026-08-10): cambió el shape de tres respuestas persistidas —
        // `zones` gana `send_off`/`rest`, `AerobicTest` gana `send_off` y
        // `missed_intervals`, y `Member.role` puede ser null. Un cache de la
        // versión anterior no los trae, y `missed_intervals.length` sobre
        // `undefined` es una pantalla en blanco, no un dato que falta. Subir el
        // buster tira ese cache; es la mitad que hay que acordarse de hacer
        // cada vez que una respuesta cambia de forma.
        // v2: se dejaron de persistir las queries de identidad.
        buster: 'v3',
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
