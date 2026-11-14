import { describe, expect, it } from 'vitest'
import type { Feasibility, SeasonResult } from '../../lib/types'
import { SIM_PARAMS_INICIALES } from './simDefaults'
import {
  fraseDeFactibilidad, fraseDeTemporada, nivelLegible, problemasDeParams,
} from './simTextos'

describe('problemasDeParams', () => {
  it('los parámetros iniciales valen', () => {
    expect(problemasDeParams(SIM_PARAMS_INICIALES)).toEqual([])
  })
  it.each([
    [{ goal: '1:09.00' }, 'más rápida'],
    [{ goal: '1:07.80' }, 'más rápida'],
    [{ current: 'abc' }, 'tiempo actual'],
    [{ goal: '' }, 'tiempo meta'],
    [{ weeks: 3 }, 'de 4 a 30'],
    [{ weeks: 31 }, 'de 4 a 30'],
    [{ weeks: 0 }, 'de 4 a 30'],      // `Number('')` al vaciar el campo
    [{ weeks: 12.5 }, 'de 4 a 30'],
    [{ km: 0 }, 'más de 0'],
  ])('%o → «%s»', (cambio, texto) => {
    const problemas = problemasDeParams({ ...SIM_PARAMS_INICIALES, ...cambio })
    expect(problemas.join(' ')).toContain(texto)
  })
  it('los límites justos valen', () => {
    expect(problemasDeParams({ ...SIM_PARAMS_INICIALES, weeks: 4 })).toEqual([])
    expect(problemasDeParams({ ...SIM_PARAMS_INICIALES, weeks: 30 })).toEqual([])
  })
})

describe('nivelLegible', () => {
  it('traduce las claves del motor', () => {
    expect(nivelLegible('competitive')).toBe('Competitivo')
    expect(nivelLegible('elite')).toBe('Élite')
    expect(nivelLegible('otra')).toBe('otra')
  })
})

const base: Feasibility = {
  status: 'aggressive', message: '', tier: 2, improvement_total: 3.3, improvement_per_micro: 1.1,
  window_min: null, window_max: 0.38, recommended_weeks: 35, extension_weeks: 23,
  realistic_ceiling: 66.66, safe_rate_per_week: 0.1, detail: {},
}

describe('fraseDeFactibilidad', () => {
  it('agresivo: lo pedido, el techo y las semanas que harían falta, sin claves internas', () => {
    const f = fraseDeFactibilidad(base, 67.8, 64.5, 12)
    expect(f).toContain('Pides un 4.9% de mejora')
    expect(f).toContain('en 12 semanas el techo realista es 1.7%')
    expect(f).toContain('unas 35 semanas (23 más)')
    expect(f).not.toMatch(/290|aggressive|Tier/)
  })
  it('realista y exigente', () => {
    expect(fraseDeFactibilidad({ ...base, status: 'ok' }, 67.8, 67.0, 12)).toContain('Cabe con margen')
    expect(fraseDeFactibilidad({ ...base, status: 'warning' }, 67.8, 67.0, 12)).toContain('sin margen')
  })
})

describe('fraseDeTemporada', () => {
  const s: SeasonResult = {
    level: 'competitive', n_macros: 3, season_start: 67.8, season_end: 65.04,
    season_improvement_s: 2.76, season_improvement_pct: 4.06,
    annual_low_pct: 2, annual_high_pct: 3.5, verdict: 'optimistic', message: '', macros: [],
  }
  it('el nivel en español y qué significa el veredicto', () => {
    const f = fraseDeTemporada(s)
    expect(f).toContain('nivel Competitivo es 2.0%–3.5% al año')
    expect(f).toContain('3 macros perfectos')
    expect(f).not.toContain('competitive')
  })
})
