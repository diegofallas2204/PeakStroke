// El PDF de la tabla individual del atleta (nota 24 del vault): su plan semana
// a semana para una prueba. Completa los otros dos —el del simulador y el de la
// tabla del equipo— con el mismo constructor (`lib/pdf.ts`).
//
// Es la hoja que se lleva el atleta o se pega en el corcho: cada semana con su
// tiempo esperado, el ritmo y, si no es el modo simple, la prescripción por zona
// (ritmo y salida), como en la tabla del equipo. El PDF solo admite Latin-1:
// nada de flechas ni rayas largas en el texto.
import type { Week } from '../../lib/types'
import { STATUS_META, STROKE_LABEL, ZONE_META, ZONE_ORDER } from '../../lib/constants'
import { signed, toClock } from '../../lib/format'
import { descargarPdf, slug } from '../../lib/pdf'
import type { EventSelection } from '../../components/ui/EventPicker'

export function descargarPlanPdf(weeks: Week[], selection: EventSelection, simple: boolean): void {
  const { plan, athlete, event } = selection
  const prueba = `${event.distance} ${STROKE_LABEL[event.stroke] ?? event.stroke}`

  const head = ['Semana', 'Fase', 'Km', 'Esperado']
  if (!simple) head.push('Ritmo /100', ...ZONE_ORDER)
  head.push('Real')
  if (!simple) head.push('Dif.')
  head.push('Estado')

  const body = weeks.map((w) => {
    const fila: string[] = [
      `S${w.week_number}  ${w.date_label}${w.is_competition ? '\nCompetencia' : ''}`,
      w.disabled ? `Parón${w.disable_reason ? `: ${w.disable_reason}` : ''}` : w.phase,
      String(w.planned_km),
      toClock(w.expected_time),
    ]
    if (!simple) {
      fila.push(toClock(w.pace_100m))
      fila.push(...ZONE_ORDER.map((z) => {
        const r = w.zones?.[z]
        return r ? `${toClock(r.mid, 1)}\nsal. ${toClock(r.send_off, 0)}` : '-'
      }))
    }
    fila.push(w.real_time != null ? toClock(w.real_time) : '-')
    if (!simple) fila.push(w.diff_seconds != null ? `${signed(w.diff_seconds)} s` : '-')
    fila.push(w.disabled ? 'Parón' : w.real_time != null ? STATUS_META[w.status ?? 'pending']?.label ?? '-' : '-')
    return fila
  })

  const primeraZona = 5
  descargarPdf({
    title: `Plan semanal · ${athlete.swimmer_name}`,
    subtitle: [
      plan.name,
      prueba,
      `de ${toClock(event.current_time)} a ${toClock(event.goal_time)}`,
      `${weeks.length} semanas`,
    ].join(' · '),
    filename: `plan-${slug(athlete.swimmer_name)}-${event.distance}-${slug(event.stroke)}`,
    tables: [{
      head,
      body,
      columnStyles: simple ? undefined : Object.fromEntries(
        ZONE_ORDER.map((z, i) => [
          primeraZona + i,
          { textColor: ZONE_META[z].color, halign: 'center' as const, cellWidth: 50 },
        ]),
      ),
      note: simple ? undefined
        : 'Tiempo por zona = punto medio del rango, por 100 m. Salida (sal.) = intervalo para '
          + 'repeticiones de 100 m, cuadrado al reloj de pared. Dif. = real menos esperado '
          + '(negativo = más rápido).',
    }],
  })
}
