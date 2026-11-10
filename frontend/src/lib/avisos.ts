// Avisos efímeros: el sitio donde un fallo se hace visible.
//
// Siete escrituras (borrar un test, apuntar el tiempo de la semana, suspender un
// macrociclo…) no enseñaban su error en ningún sitio: si el backend rechazaba la
// petición, la pantalla se quedaba igual y el usuario creía haber guardado. El
// almacén vive fuera de React porque quien avisa es `queryClient`, que no es un
// componente.
import { useSyncExternalStore } from 'react'

export type Aviso = { id: number; texto: string }

const DURACION_MS = 6000

let avisos: Aviso[] = []
let siguiente = 1
const oyentes = new Set<() => void>()

function publicar(nuevos: Aviso[]) {
  avisos = nuevos
  oyentes.forEach((o) => o())
}

export function cerrarAviso(id: number) {
  publicar(avisos.filter((a) => a.id !== id))
}

/** Enseña un error. El mismo texto no se apila dos veces. */
export function avisarError(texto: string) {
  if (avisos.some((a) => a.texto === texto)) return
  const id = siguiente++
  publicar([...avisos, { id, texto }])
  setTimeout(() => cerrarAviso(id), DURACION_MS)
}

function suscribir(oyente: () => void) {
  oyentes.add(oyente)
  return () => oyentes.delete(oyente)
}

export function useAvisos(): Aviso[] {
  return useSyncExternalStore(suscribir, () => avisos, () => avisos)
}
