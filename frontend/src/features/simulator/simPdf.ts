// El PDF del simulador: las mismas tablas que se ven en pantalla, en papel.
//
// Vive aparte de la página porque `SimulatorPage.tsx` solo orquesta, y aparte de
// `SimPlanTable.tsx` porque ese archivo solo puede exportar componentes (regla
// de fast refresh de Vite).
import type { SimulationResult, SimWeek } from '../../lib/types'
import {
  CURVE_LABEL, POOL_LABEL, SPECIALTY_LABEL, STROKE_LABEL, ZONE_META, ZONE_ORDER,
} from '../../lib/constants'
import { toClock } from '../../lib/format'
import { descargarPdf, slug } from '../../lib/pdf'
import type { TablaPdf } from '../../lib/pdf'
import type { SimParamsState } from './simDefaults'

/**
 * Descarga el plan simulado. `simple` refleja el modo de la pantalla: lo que se
 * lleva el archivo es lo que el entrenador está viendo, no otra tabla distinta.
 */
export function descargarSimPdf(
  params: SimParamsState, data: SimulationResult, simple: boolean,
): void {
  const prueba = `${params.distance}m ${STROKE_LABEL[params.stroke] ?? params.stroke}`
  const tables: TablaPdf[] = []

  if (!simple) tables.push(tablaDeZonas(data.weeks))

  tables.push({
    caption: `Plan semanal generado · ${data.weeks.length} semanas`,
    ...tablaDeSemanas(data.weeks, simple),
    note: simple
      ? undefined
      : 'Tiempo por zona = punto medio del rango (pace /100m sobre el tiempo esperado de la semana).',
  })

  if (!simple && data.extension_weeks.length > 0) {
    tables.push({
      caption: `Semanas de extensión · +${data.extension_weeks.length}`,
      ...tablaDeSemanas(data.extension_weeks, false),
      note: `El macro de ${params.weeks} sem cierra en el techo realista `
        + `(${toClock(data.feasibility.realistic_ceiling)}); estas semanas continúan al ritmo `
        + `seguro hasta la meta. No modifican el plan ni ningún cálculo.`,
    })
  }

  descargarPdf({
    title: `Plan simulado · ${prueba}`,
    subtitle: [
      `${params.current} -> ${params.goal}`,
      `${params.weeks} semanas (micro de ${params.micro})`,
      `${params.km} km totales`,
      `curva ${CURVE_LABEL[params.curve] ?? params.curve}`,
      POOL_LABEL[params.pool] ?? `${params.pool} m`,
      SPECIALTY_LABEL[params.specialty] ?? params.specialty,
    ].join(' · '),
    filename: `simulador-${slug(prueba)}`,
    tables,
  })
}

/** Semana a semana, con todas las zonas. Espejo de `SimPlanTable`. */
function tablaDeSemanas(weeks: SimWeek[], simple: boolean): Omit<TablaPdf, 'caption' | 'note'> {
  const head = ['Semana', 'Fecha', 'Fase', 'Km', 'Esperado', 'Pace /100']
  if (!simple) head.push(...ZONE_ORDER, 'Mejora', 'Acumulada')

  const body = weeks.map((w) => {
    const fila = [
      `S${w.week_number}`, w.date_label, w.phase, String(w.planned_km),
      toClock(w.expected_time), toClock(w.pace_100m),
    ]
    if (!simple) {
      fila.push(...ZONE_ORDER.map((z) => (w.zones[z] ? toClock(w.zones[z]!.mid, 1) : '—')))
      fila.push(`${w.improvement_vs_prev.toFixed(2)}s`, `${w.cumulative_improvement.toFixed(2)}s`)
    }
    return fila
  })

  return { head, body, columnStyles: estilosDeZona(simple ? -1 : 6) }
}

/**
 * Zonas de la semana 1 frente a la semana pico — las dos mitades del selector
 * de `SimZones`. En pantalla se ven de una en una; en papel no hay botón que
 * pulsar, así que van juntas.
 */
function tablaDeZonas(weeks: SimWeek[]): TablaPdf {
  const inicio = weeks[0]
  const pico = weeks[Math.max(weeks.length - 2, 0)]
  const ritmo = (w: SimWeek, z: string) => (w.zones[z] ? toClock(w.zones[z]!.mid, 1) : '—')
  const rango = (w: SimWeek, z: string) =>
    (w.zones[z] ? `${toClock(w.zones[z]!.min, 1)} - ${toClock(w.zones[z]!.max, 1)}` : '—')

  return {
    caption: 'Zonas de entrenamiento (pace /100m)',
    head: [
      'Zona', 'Nombre',
      `S${inicio.week_number} ritmo`, `S${inicio.week_number} rango`,
      `S${pico.week_number} ritmo`, `S${pico.week_number} rango`,
      'Km/sem (pico)',
    ],
    body: ZONE_ORDER.map((z) => [
      { content: z, styles: { textColor: ZONE_META[z].color, fontStyle: 'bold' as const } },
      ZONE_META[z].label,
      ritmo(inicio, z), rango(inicio, z),
      ritmo(pico, z), rango(pico, z),
      pico.zone_km[z] != null ? `${pico.zone_km[z]} km` : '—',
    ]),
    note: 'Semana 1 = arranque del macrociclo; semana pico = la anterior al taper.',
  }
}

/** Pinta las columnas de zona con su color, desde el índice indicado. */
function estilosDeZona(desde: number): TablaPdf['columnStyles'] {
  if (desde < 0) return undefined
  return Object.fromEntries(
    ZONE_ORDER.map((z, i) => [desde + i, { textColor: ZONE_META[z].color, halign: 'center' as const }]),
  )
}
