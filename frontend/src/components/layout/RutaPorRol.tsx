// Guarda de ruta por rol.
//
// Esconder una sección del menú NO la hace inalcanzable: `/equipo` se puede
// teclear en la barra de direcciones, y hasta el 2026-08-07 `App.tsx` registraba
// todas las rutas para todo el mundo. El backend responde 403 —así que no hay
// fuga de datos— pero la pantalla se quedaba a medias, con errores en vez de una
// explicación.
//
// La lista de permisos es la MISMA que la del menú (`navConfig`), a propósito:
// dos listas separadas acaban diciendo cosas distintas.
import { Navigate, useLocation } from 'react-router-dom'
import { Spinner } from '../ui/primitives'
import { useRole } from '../../hooks/useSession'
import { NAV_ITEMS, puedeVer } from './navConfig'

export function RutaPorRol({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  const role = useRole()

  // `undefined` es "todavía no se sabe", no "no tiene permiso". Decidir aquí
  // mandaría al usuario al dashboard un instante antes de saber quién es.
  if (role === undefined) return <Spinner />

  const item = NAV_ITEMS.find((i) => i.to === pathname)
  if (item && !puedeVer(item, role)) return <Navigate to="/" replace />

  return <>{children}</>
}
