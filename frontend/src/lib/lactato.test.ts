import { describe, expect, it } from 'vitest'
import { parsearBrazadas, parsearEsfuerzo, parsearNumero } from './lactato'

describe('los faltantes de la hoja del 22/09', () => {
  it.each(['', ' ', '-', '--', 'NA', 'na', "'-'", 's/d'])('«%s» es un faltante', (t) => {
    expect(parsearNumero(t)).toBeNull()
    expect(parsearEsfuerzo(t)).toBeNull()
    expect(parsearBrazadas(t)).toEqual([])
  })
})

describe('parsearNumero', () => {
  it('lee números como texto y con coma', () => {
    expect(parsearNumero("'2.4'")).toBe(2.4)
    expect(parsearNumero('168')).toBe(168)
    expect(parsearNumero('3,3')).toBe(3.3)
  })
  it('lo que no se entiende no se adivina', () => {
    expect(parsearNumero('2.4.1')).toBeUndefined()
    expect(parsearNumero('alto')).toBeUndefined()
  })
})

describe('parsearEsfuerzo', () => {
  it('un rango es su centro, nunca texto', () => {
    expect(parsearEsfuerzo('6-7')).toBe(6.5)
    expect(parsearEsfuerzo('6.5-7')).toBe(6.75)
    expect(parsearEsfuerzo('3 - 4')).toBe(3.5)
    expect(parsearEsfuerzo('8')).toBe(8)
  })
  it('fuera de la escala CR-10 no vale', () => {
    expect(parsearEsfuerzo('11')).toBeUndefined()
    expect(parsearEsfuerzo('-1')).toBeUndefined()
  })
})

describe('parsearBrazadas', () => {
  it('acepta comas, barras y espacios', () => {
    expect(parsearBrazadas('34, 36,36,36')).toEqual([34, 36, 36, 36])
    expect(parsearBrazadas('31/31/30/30')).toEqual([31, 31, 30, 30])
    expect(parsearBrazadas('31 31 30 30')).toEqual([31, 31, 30, 30])
  })
  it('un conteo imposible marca el campo', () => {
    expect(parsearBrazadas('31, 0')).toBeUndefined()
    expect(parsearBrazadas('31, 3.5')).toBeUndefined()
  })
})
