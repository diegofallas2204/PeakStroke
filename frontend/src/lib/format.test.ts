import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { fechaCorta, toShortDate } from './format'

// En Costa Rica (UTC−6) es donde se notaba: medianoche UTC es el día anterior.
beforeAll(() => { vi.stubEnv('TZ', 'America/Costa_Rica') })
afterAll(() => { vi.unstubAllEnvs() })

describe('toShortDate', () => {
  it('(control) la prueba corre de verdad en la zona de Costa Rica', () => {
    // Si la zona no cambiara, los tests de abajo pasarían por casualidad.
    expect(new Date('2026-09-22').getDate()).toBe(21)
  })

  it('una fecha sin hora es ese día, no la medianoche UTC', () => {
    // Antes: new Date('2026-09-22') = 21 sept a las 18:00 en Costa Rica.
    expect(toShortDate('2026-09-22')).toMatch(/^22 sept/)
    expect(toShortDate('2026-09-22')).toBe(fechaCorta('2026-09-22'))
  })

  it('una fecha con hora sin zona viene del backend en UTC', () => {
    // 03:00 UTC del 22 son las 21:00 del 21 en Costa Rica.
    expect(toShortDate('2026-09-22T03:00:00')).toMatch(/^21 sept/)
    expect(toShortDate('2026-09-22T03:00:00.123456')).toMatch(/^21 sept/)
  })

  it('una fecha con zona se respeta', () => {
    expect(toShortDate('2026-09-22T03:00:00Z')).toMatch(/^21 sept/)
    expect(toShortDate('2026-09-22T03:00:00+00:00')).toMatch(/^21 sept/)
    expect(toShortDate('2026-09-22T03:00:00-06:00')).toMatch(/^22 sept/)
  })

  it('sin fecha o con basura, una raya', () => {
    expect(toShortDate(null)).toBe('—')
    expect(toShortDate('')).toBe('—')
    expect(toShortDate('ayer')).toBe('—')
  })
})
