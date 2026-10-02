// Las cuatro series de la curva de carga: nombre y color. Las comparten la
// gráfica, su leyenda y las tarjetas del estado de hoy.
export const SERIES = {
  ctl: { label: 'Carga crónica (CTL)', color: 'var(--color-accent)' },
  atl: { label: 'Carga aguda (ATL)', color: 'var(--color-coral)' },
  tsb: { label: 'Balance (TSB)', color: 'var(--color-violet)' },
  stss: { label: 'Carga del día (sTSS)', color: 'var(--color-text-faint)' },
} as const
