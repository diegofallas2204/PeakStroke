// La prescripción de una zona. Vive aparte del plan porque la comparten tres
// consumidores —el plan semanal, el simulador y la tabla de equipo— y ninguno
// de los tres depende de los otros dos.

/**
 * El objetivo de una zona: a qué ritmo y cada cuánto sale la repetición.
 *
 * `mid` es el objetivo científico; `min`/`max` son ±1% de tolerancia de
 * visualización. `send_off` es el intervalo ya cuadrado al reloj de pared (5 s)
 * y `rest` el descanso real que queda dentro de ese ciclo. Las dos mitades
 * viajan juntas porque una prescripción son las dos: el ritmo solo no se puede
 * escribir en la pizarra.
 */
export type ZoneRange = {
  min: number
  mid: number
  max: number
  send_off: number
  rest: number
  rep_distance: number
} | null
export type Zones = Record<string, ZoneRange>
