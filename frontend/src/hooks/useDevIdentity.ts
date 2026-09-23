// Conmutador de desarrollo: con qué ojos se está mirando la aplicación.
//
// Son dos ejes y la separación es el punto (ver `core/dependencies.py` en el
// backend):
//
//   identidad ──▶ QUIÉN eres. La interfaz que ves es la de ese rol, fielmente:
//                 un atleta recibe 403 donde un atleta recibe 403. Sin eso no
//                 se puede revisar la UI de atleta, porque todo daría 200.
//
//   bypass    ──▶ Si además te saltas los guards de rol. Levanta lo que puedes
//                 HACER, no lo que VES: el filtro por nadador sigue puesto, así
//                 que sigues mirando la app de esa persona mientras te
//                 desatascas montando datos.
//
// Se exporta el hook **y dos getters planos**: `api.ts::request()` no es un
// componente y no puede llamar hooks, pero necesita leer el estado en cada
// petición.
import { useSyncExternalStore } from 'react'

const IDENTITY_KEY = 'ps-dev-identity'
const BYPASS_KEY = 'ps-dev-bypass'

function readIdentity(): string | null {
  if (typeof localStorage === 'undefined') return null
  return localStorage.getItem(IDENTITY_KEY) || null
}

function readBypass(): boolean {
  if (typeof localStorage === 'undefined') return false
  return localStorage.getItem(BYPASS_KEY) === 'true'
}

let identity: string | null = readIdentity()
let bypass: boolean = readBypass()

const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** El email que se está suplantando, o null para el usuario por defecto. */
export function getDevIdentity(): string | null {
  return identity
}

/** Si las peticiones deben pedir modo desarrollador. */
export function getDevBypass(): boolean {
  return bypass
}

export function setDevBypass(value: boolean) {
  bypass = value
  localStorage.setItem(BYPASS_KEY, String(value))
  listeners.forEach((l) => l())
}

/**
 * Cambia de identidad y **recarga la página**.
 *
 * Recargar es deliberado y más barato que la alternativa. Cambiar de identidad
 * invalida todo lo que hay en pantalla —datos, permisos, navegación— y también
 * cualquier mutación en vuelo; resolver eso en caliente serían decenas de
 * casos, y esto no es una función de producto sino una herramienta de
 * depuración. El `limpiar` que recibe tiene que dejar el cache en disco vacío
 * ANTES de recargar: ver `main.tsx`.
 */
export function setDevIdentity(email: string | null, limpiar: () => void) {
  identity = email
  if (email == null) localStorage.removeItem(IDENTITY_KEY)
  else localStorage.setItem(IDENTITY_KEY, email)
  limpiar()
  window.location.reload()
}

export function useDevIdentity(): string | null {
  return useSyncExternalStore(subscribe, () => identity, () => identity)
}

export function useDevBypass(): [boolean, (v: boolean) => void] {
  const value = useSyncExternalStore(subscribe, () => bypass, () => bypass)
  return [value, setDevBypass]
}
