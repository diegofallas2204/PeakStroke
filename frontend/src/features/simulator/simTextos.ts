// Lo que el simulador comprueba y dice, en funciones puras (2026-11-13).
//
// Dos cosas que vivían repartidas y que ahora se prueban (`simTextos.test.ts`):
//
//   · Qué parámetros son válidos ANTES de preguntar al motor, con los mismos
//     límites que `SimulationRequest` del backend. Antes solo se miraba que la
//     meta fuera menor que el tiempo actual: unas semanas fuera de rango
//     llegaban al motor, volvía un 422 que nadie pintaba, y en pantalla se
//     quedaban los resultados de los parámetros anteriores.
//   · Las frases del veredicto. El motor devuelve un mensaje con la clave
//     interna del nivel («competitive») y cifras sin contexto («supera el techo
//     1.68% (290%)»). Las frases se arman aquí con los números de la respuesta;
//     el motor no se toca (su texto está congelado en el snapshot de referencia).
import { tryToSeconds } from '../../lib/format'
import type { Feasibility, SeasonResult } from '../../lib/types'
import type { SimParamsState } from './simDefaults'

/** Los mismos límites que `SimulationRequest` (backend/app/api/v1/simulador/schemas.py). */
export const SEMANAS_MIN = 4
export const SEMANAS_MAX = 30

/** Lo que impide simular, en frases. Vacía = se puede. */
export function problemasDeParams(p: SimParamsState): string[] {
  const problemas: string[] = []
  const actual = tryToSeconds(p.current)
  const meta = tryToSeconds(p.goal)
  if (actual == null) problemas.push('El tiempo actual no se entiende: usa m:ss.cc (1:07.80) o ss.cc.')
  if (meta == null) problemas.push('El tiempo meta no se entiende: usa m:ss.cc (1:04.50) o ss.cc.')
  if (actual != null && meta != null && meta >= actual) {
    problemas.push('La meta tiene que ser más rápida que el tiempo actual.')
  }
  if (!Number.isInteger(p.weeks) || p.weeks < SEMANAS_MIN || p.weeks > SEMANAS_MAX) {
    problemas.push(`Las semanas van de ${SEMANAS_MIN} a ${SEMANAS_MAX}.`)
  }
  if (!(p.km > 0)) problemas.push('Los kilómetros totales tienen que ser más de 0.')
  return problemas
}

const NIVEL: Record<string, string> = {
  beginner: 'Principiante', recreational: 'Recreativo', advanced: 'Avanzado',
  competitive: 'Competitivo', elite: 'Élite',
}

/** `competitive` → `Competitivo`. Una clave desconocida se enseña tal cual. */
export function nivelLegible(clave: string): string {
  return NIVEL[clave] ?? clave
}

// Con punto, como el resto de la app y los tiempos de natación (1:07.80).
const pct = (x: number) => `${x.toFixed(1)}%`

/**
 * El veredicto del macro en una o dos frases, con los números de la respuesta.
 * `actual` y `meta` en segundos; `semanas` las del plan.
 */
export function fraseDeFactibilidad(
  f: Feasibility, actual: number, meta: number, semanas: number,
): string {
  const pedida = ((actual - meta) / actual) * 100
  const techo = ((actual - f.realistic_ceiling) / actual) * 100
  const base = `Pides un ${pct(pedida)} de mejora; en ${semanas} semanas el techo realista es ${pct(techo)}.`
  if (f.status === 'ok') return `${base} Cabe con margen.`
  if (f.status === 'warning') return `${base} Cabe, pero sin margen: cualquier parón se nota.`
  if (f.recommended_weeks != null) {
    const extra = f.recommended_weeks - semanas
    return `${base} Para llegar harían falta unas ${f.recommended_weeks} semanas (${extra} más).`
  }
  return `${base} No cabe en este macro.`
}

/** La proyección de temporada: el rango típico del nivel y qué significa el techo. */
export function fraseDeTemporada(s: SeasonResult): string {
  const rango = `Lo típico para nivel ${nivelLegible(s.level)} es ${pct(s.annual_low_pct)}–${pct(s.annual_high_pct)} al año.`
  if (s.verdict === 'ok') return `${rango} Este techo entra en ese rango.`
  if (s.verdict === 'optimistic') {
    return `${rango} Este es el máximo con ${s.n_macros} macros perfectos, no lo esperable.`
  }
  return `${rango} Se sale de lo realista: revisa el tiempo actual o la prueba.`
}
