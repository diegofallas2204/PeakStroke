// TODO-31: nunca dos `/auth/refresh` a la vez, ni dentro de una pestaña ni
// entre dos. Las «pestañas» son dos instancias de `unSoloVuelo` que comparten
// un cerrojo, que es justo lo que comparten dos pestañas de verdad.
import { describe, expect, it } from 'vitest'
import { unSoloVuelo, type Cerrojos } from './unSoloVuelo'

/** `navigator.locks` de mentira: una cola, como el de verdad en modo exclusivo. */
function cerrojosCompartidos(): Cerrojos {
  let cola: Promise<unknown> = Promise.resolve()
  return {
    request<T>(_nombre: string, tarea: () => Promise<T>): Promise<T> {
      const turno = cola.then(tarea, tarea)
      cola = turno.catch(() => undefined)
      return turno
    },
  }
}

/** Un «servidor» que cuenta cuántos refresh tiene en vuelo a la vez. */
function servidor() {
  const estado = { llamadas: 0, enVuelo: 0, maximoALaVez: 0 }
  const pedir = async () => {
    estado.llamadas += 1
    estado.enVuelo += 1
    estado.maximoALaVez = Math.max(estado.maximoALaVez, estado.enVuelo)
    await new Promise((r) => setTimeout(r, 15))
    estado.enVuelo -= 1
    return estado.llamadas
  }
  return { estado, pedir }
}

describe('unSoloVuelo', () => {
  it('dentro de una pestaña, cinco 401 a la vez son una sola petición', async () => {
    const { estado, pedir } = servidor()
    const refrescar = unSoloVuelo(pedir, cerrojosCompartidos())

    const resultados = await Promise.all([1, 2, 3, 4, 5].map(() => refrescar()))

    expect(estado.llamadas).toBe(1)
    expect(new Set(resultados).size).toBe(1)
  })

  it('dos pestañas a la vez hacen cola: nunca hay dos refresh en vuelo', async () => {
    const { estado, pedir } = servidor()
    const cerrojos = cerrojosCompartidos()
    const pestanaA = unSoloVuelo(pedir, cerrojos)
    const pestanaB = unSoloVuelo(pedir, cerrojos)

    await Promise.all([pestanaA(), pestanaB(), pestanaA(), pestanaB()])

    // Cada pestaña necesita su access token, así que son dos peticiones; lo
    // que el servidor no puede ver nunca es las dos a la vez.
    expect(estado.llamadas).toBe(2)
    expect(estado.maximoALaVez).toBe(1)
  })

  it('sin cerrojos entre pestañas, dos pestañas sí chocan (lo que se evita)', async () => {
    const { estado, pedir } = servidor()
    const pestanaA = unSoloVuelo(pedir, undefined)
    const pestanaB = unSoloVuelo(pedir, undefined)

    await Promise.all([pestanaA(), pestanaB()])

    expect(estado.maximoALaVez).toBe(2)
  })

  it('terminada una, la siguiente llamada vuelve a pedir', async () => {
    const { estado, pedir } = servidor()
    const refrescar = unSoloVuelo(pedir, cerrojosCompartidos())

    await refrescar()
    await refrescar()

    expect(estado.llamadas).toBe(2)
  })

  it('un fallo llega a todos los que esperaban y no deja el cerrojo cogido', async () => {
    let falla = true
    const pedir = async () => {
      await new Promise((r) => setTimeout(r, 5))
      if (falla) throw new Error('sin red')
      return 'ok'
    }
    const refrescar = unSoloVuelo(pedir, cerrojosCompartidos())

    const [a, b] = await Promise.allSettled([refrescar(), refrescar()])
    expect([a.status, b.status]).toEqual(['rejected', 'rejected'])

    falla = false
    await expect(refrescar()).resolves.toBe('ok')
  })
})
