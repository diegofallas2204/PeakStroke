// Plan semanal: un módulo, tres vistas sobre los mismos datos.
//
// Comparación era una sección aparte que pedía la MISMA query `['weeks', id]`
// con el mismo selector y dibujaba el mismo gráfico: dos entradas de menú para
// un solo trabajo. Aquí los datos se piden una vez y cada vista responde a una
// pregunta distinta sobre ellos: qué toca esta semana (Plan), cómo va contra el
// plan (Progresión) y a qué ritmo se nada (Zonas).
//
// El selector y la query viven en el shell, POR ENCIMA del switch de vistas, y
// eso es el punto de la fusión: si vivieran dentro de cada vista, cambiar de
// pestaña las desmontaría y la selección —macrociclo, atleta, prueba— se
// perdería en cada clic, que es exactamente lo que pasaba al saltar de Plan
// semanal a Comparación.
//
// La vista viaja en la URL (`?vista=`) y no en un estado local: así el atrás
// del navegador funciona y una vista se puede marcar y compartir. Va en query
// param y no en subruta porque `navConfig` compara la ruta EXACTA en tres
// sitios (menú, guarda y rótulo móvil) y `SECTION_ACCENT` indexa por ruta: el
// pathname es la identidad de la sección y no debe moverse.
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { ListChecks } from 'lucide-react'
import { api } from '../../lib/api'
import { SECTION_ACCENT } from '../../lib/constants'
import { usePageEnter } from '../../hooks/usePageEnter'
import { useVacio } from '../../hooks/useVacio'
import { PageHeader } from '../../components/layout/PageHeader'
import { EmptyState, Segmented, Spinner } from '../../components/ui/primitives'
import { EventPicker, type EventSelection } from '../../components/ui/EventPicker'
import { VISTAS, vistaDesdeParam, type VistaId } from './vistas'
import { VistaPlan } from './VistaPlan'
import { VistaProgresion } from './VistaProgresion'
import { VistaZonas } from './VistaZonas'

export function WeeklyPage() {
  const [selection, setSelection] = useState<EventSelection | null>(null)
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null)
  const [params, setParams] = useSearchParams()

  const vista = vistaDesdeParam(params.get('vista'))
  const def = VISTAS.find((v) => v.id === vista) ?? VISTAS[0]
  // La vista por defecto no ensucia la URL: `/plan-semanal` a secas es Plan.
  const irA = (id: VistaId) => setParams(id === 'plan' ? {} : { vista: id })

  const { data: weeks, isLoading } = useQuery({
    queryKey: ['weeks', selection?.event.id],
    queryFn: () => api.plans.eventWeeks(selection!.event.id),
    enabled: selection != null,
  })

  // La semana enfocada es del módulo, no de una vista: la fila que se clica en
  // Plan es la que abre Zonas.
  const focusWeek = useMemo(() => {
    if (!weeks) return null
    return weeks.find((w) => w.week_number === selectedWeek)
      ?? weeks.find((w) => w.week_number === selection?.plan.current_week)
      ?? weeks[0]
      ?? null
  }, [weeks, selectedWeek, selection])

  // Un atleta no crea macrociclos ni asigna a nadie: pedírselo sería una pared.
  const vacioTitulo = useVacio('Sin datos para mostrar', 'Todavía no tienes plan semanal')
  const vacioPista = useVacio(
    'Crea un macrociclo y asigna atletas con sus pruebas para generar el plan.',
    'Cuando tu entrenador te inscriba en un macrociclo con tus pruebas objetivo, aquí verás tu progresión semana a semana.',
  )
  const ref = usePageEnter([selection?.event.id, isLoading, vista])

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Plan semanal"
        subtitle={def.subtitle}
        actions={
          <Segmented
            label="Vista del plan semanal"
            value={vista}
            onChange={irA}
            accent={SECTION_ACCENT['/plan-semanal']}
            options={VISTAS.map(({ id, label, icon: Icon }) => ({
              value: id,
              label: (
                <span className="flex items-center gap-1.5">
                  <Icon size={12.5} strokeWidth={2.2} />
                  {label}
                </span>
              ),
            }))}
          />
        }
      />
      <EventPicker onChange={setSelection} />

      {!selection ? (
        <EmptyState icon={<ListChecks size={24} />} title={vacioTitulo} hint={vacioPista} />
      ) : isLoading || !weeks ? (
        <Spinner />
      ) : vista === 'progresion' ? (
        <VistaProgresion weeks={weeks} selection={selection} />
      ) : vista === 'zonas' ? (
        <VistaZonas
          weeks={weeks}
          week={focusWeek}
          specialty={selection.athlete.specialty}
          currentWeek={selection.plan.current_week}
          onSelectWeek={setSelectedWeek}
        />
      ) : (
        <VistaPlan
          weeks={weeks}
          eventId={selection.event.id}
          currentWeek={selection.plan.current_week}
          focusWeek={focusWeek}
          onSelectWeek={setSelectedWeek}
          onVerZonas={() => irA('zonas')}
        />
      )}
    </div>
  )
}
