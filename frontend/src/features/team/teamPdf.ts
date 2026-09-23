// El PDF de la tabla del equipo: los tiempos a exigir esa semana, por atleta.
//
// Es el papel que se baja a la piscina, así que cada celda de zona lleva la
// prescripción COMPLETA —ritmo, salida y km—: el ritmo solo no se puede cantar.
import type { TeamWeek } from '../../lib/types'
import { SPECIALTY_LABEL, STATUS_META, ZONE_META, ZONE_ORDER } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { descargarPdf, slug } from '../../lib/pdf'

/**
 * Descarga la semana que se está viendo. `simple` refleja el modo de pantalla:
 * el archivo se lleva la misma tabla que el entrenador tiene delante.
 */
export function descargarEquipoPdf(
  data: TeamWeek, planName: string | undefined, totalWeeks: number, simple: boolean,
): void {
  const head = ['Atleta', 'Prueba', 'Esperado']
  if (!simple) head.push('Pace /100', ...ZONE_ORDER)
  head.push('Km', 'Real', 'Estado')

  const body = data.rows.map((row) => {
    const fila: string[] = [
      simple ? row.name : `${row.name}\n${SPECIALTY_LABEL[row.specialty] ?? row.specialty}`,
      row.event_label,
      toClock(row.expected_time),
    ]
    if (!simple) {
      fila.push(toClock(row.pace_100m))
      fila.push(...ZONE_ORDER.map((z) => celdaDeZona(row.zones?.[z], row.zone_km?.[z])))
    }
    fila.push(
      row.planned_km != null ? String(row.planned_km) : '—',
      toClock(row.real_time),
      row.disabled ? 'Parón' : STATUS_META[row.status ?? 'pending']?.label ?? '—',
    )
    return fila
  })

  const primeraZona = 4
  descargarPdf({
    title: `Tabla del equipo · Semana ${data.week_number}`,
    subtitle: [
      planName,
      data.date_label,
      data.phase ? `Fase ${data.phase}` : null,
      `Semana ${data.week_number} de ${totalWeeks}`,
      'tiempos a exigir por zona (pace /100m)',
    ].filter(Boolean).join(' · '),
    filename: `equipo-semana-${data.week_number}${planName ? `-${slug(planName)}` : ''}`,
    tables: [{
      head,
      body,
      columnStyles: simple ? undefined : Object.fromEntries(
        ZONE_ORDER.map((z, i) => [
          primeraZona + i,
          { textColor: ZONE_META[z].color, halign: 'center' as const, cellWidth: 52 },
        ]),
      ),
      note: simple ? undefined
        : 'Tiempo por zona = punto medio del rango (factores por distancia de la prueba). '
          + 'Salida (sal.) = intervalo para repeticiones de 100m, cuadrado al reloj de pared; '
          + 'el descanso crece con la intensidad de la zona. '
          + 'Km por zona = distribución sugerida según la especialidad del atleta.',
    }],
  })
}

/** 'Ritmo / salida / km' en tres líneas — la celda que se lee en el bordillo. */
function celdaDeZona(
  range: { mid: number; send_off: number } | null | undefined,
  km: number | null | undefined,
): string {
  if (!range) return '—'
  const lineas = [toClock(range.mid, 1), `sal. ${toClock(range.send_off, 0)}`]
  if (km != null) lineas.push(`${km} km`)
  return lineas.join('\n')
}
