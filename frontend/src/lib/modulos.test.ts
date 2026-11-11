import { describe, expect, it } from 'vitest'
import { moduloDe, parsearModulos, rutaActiva } from './modulos'

describe('moduloDe', () => {
  it.each([
    ['/', 'inicio'],
    ['/atletas', 'atletas'],
    ['/atletas/5', 'atletas'],
    ['/plan-semanal?atleta=2&vista=zonas', 'plan-semanal'],
    ['/entrenamiento?nueva=1', 'entrenamiento'],
    ['/perfil', 'perfil'],
  ])('%s es de %s', (ruta, modulo) => {
    expect(moduloDe(ruta)).toBe(modulo)
  })
})

describe('parsearModulos', () => {
  it('vacío o «todos» es todos', () => {
    expect(parsearModulos(undefined)).toBeNull()
    expect(parsearModulos('')).toBeNull()
    expect(parsearModulos(' todos ')).toBeNull()
  })
  it('una lista, sin espacios ni mayúsculas', () => {
    expect(parsearModulos(' Inicio, atletas ,')).toEqual(new Set(['inicio', 'atletas']))
  })
})

describe('rutaActiva', () => {
  const soloInicio = parsearModulos('inicio')

  it('con todos, todo', () => {
    expect(rutaActiva('/simulador', null)).toBe(true)
  })
  it('solo Inicio: Inicio sí, las demás secciones no', () => {
    expect(rutaActiva('/', soloInicio)).toBe(true)
    expect(rutaActiva('/equipo', soloInicio)).toBe(false)
    expect(rutaActiva('/plan-semanal?vista=progresion', soloInicio)).toBe(false)
    expect(rutaActiva('/atletas/3', soloInicio)).toBe(false)
  })
  it('Perfil es del sistema: está en cualquier build', () => {
    expect(rutaActiva('/perfil', soloInicio)).toBe(true)
    expect(rutaActiva('/perfil', parsearModulos('atletas'))).toBe(true)
  })
})
