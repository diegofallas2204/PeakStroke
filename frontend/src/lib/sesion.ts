// La sesión del cliente con el login encendido (TODO-32).
//
//   · El **access token vive solo en memoria**: ni localStorage ni cookie. Un
//     script inyectado no lo encuentra en ningún almacén, y recargar la página
//     lo pierde a propósito — se recupera con el refresh.
//   · El **refresh** viaja en su cookie httpOnly; este archivo nunca lo ve.
//     Renovar es `POST /auth/refresh`, y nunca hay dos a la vez (`unSoloVuelo`).
//   · Al salir —o al entrar otra persona— **se borra todo lo guardado en el
//     navegador**: el cache persistido de datos deportivos y el macrociclo
//     elegido. localStorage es del navegador, no de la cuenta.
//
// Con `PEAKSTROKE_AUTH_ENABLED=false` nada de esto se usa: no hay token, el
// backend atribuye cada petición a la cuenta de desarrollo y `App` no monta la
// puerta de sesión.
//
// No importa `api.ts` (que sí importa esto): las tres llamadas de sesión van
// con `fetch` a secas. Tampoco pasan por el reintento del 401 — son ellas las
// que lo resuelven.
import { useSyncExternalStore } from 'react'
import { olvidarSeleccion } from '../hooks/useSelectedPlan'
import { limpiarCacheDeIdentidad, queryClient } from './queryClient'
import type { Member, SessionResponse } from './types'
import { unSoloVuelo } from './unSoloVuelo'

const AUTH = '/api/v1/auth'
// De quién son los datos guardados en este navegador. Solo el id: sirve para
// saber si quien entra es otra persona y hay que tirarlos.
const ULTIMA_CUENTA = 'ps-ultima-cuenta'
const CANAL = 'peakstroke-auth'

/** `cargando`: aún no se sabe si la cookie de refresh sirve. */
export type EstadoDeSesion = 'cargando' | 'dentro' | 'fuera'

let token: string | null = null
let estado: EstadoDeSesion = 'cargando'
const oyentes = new Set<() => void>()

function fijarEstado(nuevo: EstadoDeSesion) {
  if (estado === nuevo) return
  estado = nuevo
  oyentes.forEach((o) => o())
}

function suscribir(oyente: () => void) {
  oyentes.add(oyente)
  return () => oyentes.delete(oyente)
}

export function useEstadoDeSesion(): EstadoDeSesion {
  return useSyncExternalStore(suscribir, () => estado, () => estado)
}

/** El access token en curso, o `null`. Lo lee `api.ts` en cada petición. */
export function getAccessToken(): string | null {
  return token
}

// ── Otras pestañas ───────────────────────────────────────────────────────────
// Entrar o salir en una pestaña cambia la cookie de todas. Las demás recargan:
// es más barato que resolver en caliente qué de lo que tienen en pantalla sigue
// siendo de quien ahora tiene la sesión.
const canal = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel(CANAL)
canal?.addEventListener('message', () => window.location.reload())
const avisarALasDemas = () => canal?.postMessage('cambio')

// ── Entrar y salir ───────────────────────────────────────────────────────────

function borrarLoGuardado() {
  limpiarCacheDeIdentidad()
  olvidarSeleccion()
}

function entrar(sesion: SessionResponse) {
  const id = String(sesion.user.id)
  // Otra persona en el mismo navegador no hereda ni un dato de la anterior.
  if (localStorage.getItem(ULTIMA_CUENTA) !== id) borrarLoGuardado()
  localStorage.setItem(ULTIMA_CUENTA, id)
  token = sesion.access_token
  queryClient.setQueryData<Member>(['session'], sesion.user)
  fijarEstado('dentro')
}

function quedarFuera() {
  token = null
  localStorage.removeItem(ULTIMA_CUENTA)
  borrarLoGuardado()
  fijarEstado('fuera')
}

async function detalle(res: Response): Promise<string> {
  try {
    const cuerpo = await res.json()
    if (typeof cuerpo.detail === 'string') return cuerpo.detail
  } catch { /* sin cuerpo JSON */ }
  return res.statusText
}

/**
 * Renueva el par de tokens. `true` si hay sesión; `false` si la cookie ya no
 * sirve (y entonces la app queda fuera). Un fallo de red o del servidor
 * **lanza** y no echa a nadie: no saber no es lo mismo que no tener sesión.
 */
export const refrescar: () => Promise<boolean> = unSoloVuelo(async () => {
  const res = await fetch(`${AUTH}/refresh`, { method: 'POST' })
  if (res.status === 401) {
    quedarFuera()
    return false
  }
  if (!res.ok) throw new Error(await detalle(res))
  entrar(await res.json() as SessionResponse)
  return true
}, typeof navigator === 'undefined' ? undefined : navigator.locks)

/** Al cargar la página: ¿la cookie de refresh abre una sesión? */
export async function arrancarSesion(): Promise<void> {
  if (estado !== 'cargando') return
  try {
    await refrescar()
  } catch {
    // Backend caído o error del servidor: a la pantalla de login, que es desde
    // donde se puede volver a intentar. No se borra nada guardado.
    fijarEstado('fuera')
  }
}

export async function iniciarSesion(email: string, password: string): Promise<void> {
  const res = await fetch(`${AUTH}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (res.status === 429) {
    const segundos = Number(res.headers.get('Retry-After'))
    throw new Error(
      Number.isFinite(segundos) && segundos > 0
        ? `Demasiados intentos. Vuelve a probar en ${esperaLegible(segundos)}.`
        : await detalle(res),
    )
  }
  if (!res.ok) throw new Error(await detalle(res))
  entrar(await res.json() as SessionResponse)
  avisarALasDemas()
}

/** Tras `POST /auth/me/password`: los tokens viejos murieron; estos son los nuevos. */
export function adoptarSesion(sesion: SessionResponse) {
  entrar(sesion)
}

/**
 * Cierra la sesión de este dispositivo, o la de todos con `todas`.
 *
 * Se sale **aunque la petición falle**: quien pulsa «salir» tiene que acabar
 * fuera de esta pantalla. Si el servidor no se enteró, la cookie caduca sola y
 * el access token no sobrevive a esta pestaña.
 */
export async function cerrarSesion(todas = false): Promise<void> {
  try {
    await fetch(`${AUTH}/${todas ? 'logout-all' : 'logout'}`, { method: 'POST' })
  } finally {
    quedarFuera()
    avisarALasDemas()
  }
}

function esperaLegible(segundos: number): string {
  if (segundos < 60) return `${segundos} s`
  const minutos = Math.ceil(segundos / 60)
  return `${minutos} min`
}
