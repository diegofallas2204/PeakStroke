import { describe, expect, it } from 'vitest'
import { confirmar, responder } from './confirmar'

describe('confirmar', () => {
  it('resuelve con lo que se responda', async () => {
    const si = confirmar({ titulo: '¿Borrar?', accion: 'Borrar' })
    responder(true)
    await expect(si).resolves.toBe(true)

    const no = confirmar({ titulo: '¿Borrar?', accion: 'Borrar' })
    responder(false)
    await expect(no).resolves.toBe(false)
  })

  it('una confirmación nueva cancela la anterior: nunca dos abiertas', async () => {
    const primera = confirmar({ titulo: 'Uno', accion: 'Sí' })
    const segunda = confirmar({ titulo: 'Dos', accion: 'Sí' })
    await expect(primera).resolves.toBe(false)
    responder(true)
    await expect(segunda).resolves.toBe(true)
  })

  it('responder sin nada abierto no hace nada', () => {
    expect(() => responder(true)).not.toThrow()
  })
})
