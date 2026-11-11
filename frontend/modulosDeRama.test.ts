import { describe, expect, it } from 'vitest'
import { moduloDeRama } from './modulosDeRama'

describe('moduloDeRama', () => {
  it.each([
    ['modulo/inicio', 'inicio'],
    ['modulo/plan-semanal', 'plan-semanal'],
    ['refs/heads/modulo/atletas', 'atletas'],
    ['Preliminar', ''],
    ['main', ''],
    ['', ''],
  ])('%s → «%s»', (rama, modulo) => {
    expect(moduloDeRama(rama)).toBe(modulo)
  })
})
