// Un solo `/auth/refresh` en vuelo por navegador (TODO-31).
//
// El refresh **solo sirve una vez**: el servidor rota la cookie en cada uso y
// trata como robo una rotación gastada que reaparece (cierra esa sesión). Dos
// pestañas comparten la cookie, así que si las dos refrescan a la vez —el caso
// normal al volver al equipo con el access caducado— la segunda llega con la
// rotación que la primera acaba de gastar: las dos fuera, y un `REFRESH_REUSADO`
// falso en la auditoría. El servidor no puede distinguirlo de una cookie
// copiada (y aceptar la rotación anterior «un ratito» dejaría pasar la copiada).
//
// Dos cerrojos, uno dentro de otro:
//
//   · dentro de la pestaña, todas las peticiones que se encuentran un 401 a la
//     vez comparten UNA promesa: una sola llamada, no una por petición;
//   · entre pestañas, `navigator.locks` las pone en fila. No hace falta
//     repartir el token: la segunda pestaña entra cuando la primera ya recibió
//     su `Set-Cookie`, así que manda la rotación nueva y recibe la suya.
//
// Sin `navigator.locks` (Safari < 15.4) queda solo el primero: dos pestañas
// pueden chocar como antes. No se finge un cerrojo que no existe.
//
// Vive aparte de `sesion.ts`, sin importar nada, para poder probarlo solo.

/** Lo que hace falta de `navigator.locks`. */
export type Cerrojos = {
  request<T>(nombre: string, tarea: () => Promise<T>): Promise<T>
}

export const NOMBRE_DEL_CERROJO = 'peakstroke-refresh'

/**
 * Envuelve `pedir` para que nunca haya dos en vuelo.
 *
 * Quien llama mientras hay una en curso recibe **esa misma** promesa, con su
 * mismo resultado o su mismo error.
 */
export function unSoloVuelo<T>(
  pedir: () => Promise<T>,
  cerrojos: Cerrojos | undefined,
): () => Promise<T> {
  let enVuelo: Promise<T> | null = null
  return () => {
    if (enVuelo === null) {
      const tarea = cerrojos
        ? cerrojos.request(NOMBRE_DEL_CERROJO, pedir)
        : pedir()
      enVuelo = tarea.finally(() => { enVuelo = null })
    }
    return enVuelo
  }
}
