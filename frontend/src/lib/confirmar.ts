// Pedir confirmación con un diálogo de la app, no con `confirm()` del navegador
// (2026-11-13, `modulo/macrociclos`).
//
// `confirm()` no lleva el estilo de la app, en móvil es una ventana del sistema
// sin contexto, y su botón dice «Aceptar» en vez de lo que va a pasar. Este
// diálogo dice la acción en el botón («Eliminar») y la marca en rojo cuando no
// tiene vuelta. Se usa igual que `confirm()`, pero esperando:
//
//     if (await confirmar({ titulo: '¿Eliminar…?', accion: 'Eliminar', peligro: true })) …
//
// El almacén vive fuera de React (como `avisos.ts`) para poder pedirlo desde un
// manejador cualquiera; lo pinta `components/ui/Confirmaciones`, montado en `App`.
import { useSyncExternalStore } from 'react'

export type PeticionDeConfirmacion = {
  titulo: string
  /** Lo que pasa y si se puede deshacer. Opcional. */
  texto?: string
  /** El verbo del botón: «Eliminar», «Quitar», «Revocar». */
  accion: string
  /** No tiene vuelta (o casi): el botón va en rojo. */
  peligro?: boolean
}

type Pendiente = PeticionDeConfirmacion & { responder: (si: boolean) => void }

let pendiente: Pendiente | null = null
const oyentes = new Set<() => void>()

function publicar(nueva: Pendiente | null) {
  pendiente = nueva
  oyentes.forEach((o) => o())
}

/** Abre el diálogo. Resuelve `true` si se confirma y `false` si se cancela. */
export function confirmar(peticion: PeticionDeConfirmacion): Promise<boolean> {
  // Una confirmación nueva cancela la que hubiera abierta: nunca dos a la vez.
  pendiente?.responder(false)
  return new Promise((resolve) => {
    publicar({ ...peticion, responder: resolve })
  })
}

/** Lo llama el diálogo al pulsar uno de sus botones (o Escape). */
export function responder(si: boolean) {
  const actual = pendiente
  publicar(null)
  actual?.responder(si)
}

function suscribir(oyente: () => void) {
  oyentes.add(oyente)
  return () => oyentes.delete(oyente)
}

export function useConfirmacionPendiente(): PeticionDeConfirmacion | null {
  return useSyncExternalStore(suscribir, () => pendiente, () => pendiente)
}
