// Forma y valores iniciales de los parámetros del simulador.
// Vive aparte de `SimParams.tsx` porque ese archivo solo puede exportar
// componentes (regla de fast refresh); aquí van el tipo y la constante.

export interface SimParamsState {
  distance: number
  stroke: string
  current: string
  goal: string
  weeks: number
  micro: number
  km: number
  curve: string
  pool: string
  specialty: string
}

export const SIM_PARAMS_INICIALES: SimParamsState = {
  distance: 100, stroke: 'mariposa', current: '1:07.80', goal: '1:04.50',
  weeks: 12, micro: 4, km: 320, curve: 'science', pool: '50', specialty: 'velocidad',
}
