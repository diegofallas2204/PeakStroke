// La puerta de la aplicación: decide si se ve la app, el login o nada todavía.
//
//   /auth/config ──▶ login apagado ──────────────────────────▶ la app, como siempre
//        │
//        └────────▶ login encendido ──▶ ¿la cookie abre sesión?
//                                          cargando ──▶ espera (ni app ni login)
//                                          fuera    ──▶ pantalla de login
//                                          dentro   ──▶ ¿contraseña temporal?
//                                                         sí ──▶ cambiarla
//                                                         no ──▶ la app
//
// «Cargando» no es «fuera»: enseñar el login un instante a quien sí tiene
// sesión —cada recarga, mientras llega el refresh— es un parpadeo que además
// invita a teclear la contraseña sin necesidad.
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { RefreshCw, ServerOff } from 'lucide-react'
import { EmptyState, Spinner } from '../../components/ui/primitives'
import { useAuthConfig, useSession } from '../../hooks/useSession'
import { arrancarSesion, useEstadoDeSesion } from '../../lib/sesion'
import { CambioObligado } from './CambioObligado'
import { LoginPage } from './LoginPage'

export function PuertaDeSesion({ children }: { children: ReactNode }) {
  const { data: config, isError, isFetching, refetch } = useAuthConfig()
  const estado = useEstadoDeSesion()
  const conLogin = config?.auth_enabled === true

  useEffect(() => {
    if (conLogin) void arrancarSesion()
  }, [conLogin])

  // Sin `/auth/config` no se sabe ni en qué modo está la app. Antes se pintaba
  // igualmente y cada sección fallaba por su cuenta, como si estuviera vacía.
  if (isError && !config) {
    return (
      <div className="relative z-10 flex min-h-full w-full items-center justify-center">
        <EmptyState
          icon={<ServerOff size={24} />}
          title="No se pudo conectar con el servidor"
          hint="Comprueba que el backend esté corriendo y vuelve a intentar."
          action={
            <button className="btn btn-primary" onClick={() => void refetch()} disabled={isFetching}>
              <RefreshCw size={14} /> Reintentar
            </button>
          }
        />
      </div>
    )
  }
  if (!config) return <Centrado><Spinner /></Centrado>
  if (!conLogin) return <>{children}</>
  if (estado === 'cargando') return <Centrado><Spinner /></Centrado>
  if (estado === 'fuera') return <LoginPage />
  return <Dentro>{children}</Dentro>
}

/** Ya hay sesión: falta saber si su contraseña es una temporal. */
function Dentro({ children }: { children: ReactNode }) {
  const { data: session } = useSession()
  if (!session) return <Centrado><Spinner /></Centrado>
  if (session.must_change_password) return <CambioObligado nombre={session.name} />
  return <>{children}</>
}

function Centrado({ children }: { children: ReactNode }) {
  return <div className="relative z-10 flex min-h-full w-full items-center justify-center">{children}</div>
}
