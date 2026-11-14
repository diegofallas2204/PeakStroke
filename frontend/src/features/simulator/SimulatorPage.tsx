// Simulador de escenarios: parámetros en vivo contra el motor de predicción,
// con análisis de factibilidad, comparación de curvas y plan resultante.
// La página solo orquesta: cada bloque de resultado vive en su propio componente.
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import { tryToSeconds } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { useSimpleMode } from '../../hooks/useSimpleMode'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, Spinner } from '../../components/ui/primitives'
import { ErrorDeCarga } from '../../components/ui/ErrorDeCarga'
import { problemasDeParams } from './simTextos'
import { BotonPdf } from '../../components/ui/BotonPdf'
import { SIM_PARAMS_INICIALES } from './simDefaults'
import { descargarSimPdf } from './simPdf'
import { SimParams } from './SimParams'
import { SimFeasibility } from './SimFeasibility'
import { SimSeason } from './SimSeason'
import { SimCurveChart } from './SimCurveChart'
import { SimPlanTable } from './SimPlanTable'
import { SimExtensionTable } from './SimExtension'
import { SimZones } from './SimZones'

export function SimulatorPage() {
  const [params, setParams] = useState(SIM_PARAMS_INICIALES)
  const [debounced, setDebounced] = useState(params)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(params), 300)
    return () => clearTimeout(t)
  }, [params])

  const current = tryToSeconds(debounced.current)
  const goal = tryToSeconds(debounced.goal)
  // Con los mismos límites que el backend: lo que no pase aquí no llega al
  // motor (antes, unas semanas fuera de rango volvían como un 422 que nadie
  // pintaba). Los problemas se dicen al lado del formulario.
  const problemas = problemasDeParams(params)
  const valid = problemasDeParams(debounced).length === 0

  const { data, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['sim', debounced],
    queryFn: () => api.simulator.run({
      distance: debounced.distance, stroke: debounced.stroke,
      current_time: current, goal_time: goal,
      total_weeks: debounced.weeks, weeks_per_micro: debounced.micro,
      total_km: debounced.km, curve: debounced.curve, pool: debounced.pool,
      specialty: debounced.specialty,
    }),
    enabled: valid,
    placeholderData: (prev) => prev,
  })

  // Proyección ANUAL: temporada = 3 macrociclos encadenados (motor de dominio).
  // Solo depende del tiempo actual y la prueba (no de la meta ni las semanas).
  const { data: season, isError: seasonFallo } = useQuery({
    queryKey: ['season', debounced.distance, debounced.stroke, current, debounced.pool],
    queryFn: () => api.simulator.season({
      distance: debounced.distance, stroke: debounced.stroke,
      current_time: current, pool: debounced.pool, n_macros: 3,
    }),
    enabled: valid,
    placeholderData: (prev) => prev,
  })

  const [simple] = useSimpleMode()
  const ref = usePageEnter([])
  const feasibility = data?.feasibility

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Simulador de escenarios"
        subtitle="Prueba metas y semanas: recalcula al momento y no toca los planes guardados"
      />

      <div className="flex flex-col gap-4">
        {/* ── Parámetros (fila superior, a todo el ancho) ── */}
        <SimParams params={params} setParams={setParams} problemas={problemas} />

        {/* ── Resultados ── */}
        {/* Los resultados son SIEMPRE de los parámetros de arriba: con unos
            inválidos o un fallo del motor no se enseñan los de antes como si
            fueran estos, y mientras recalcula se atenúan. */}
        <div
          className="flex flex-col gap-4 transition-opacity duration-200"
          style={{ opacity: isFetching && data ? 0.55 : 1 }}
          aria-busy={isFetching}
        >
          {valid && isError && (
            <ErrorDeCarga error={error} que="la simulación" onReintentar={() => void refetch()} reintentando={isFetching} />
          )}
          {valid && !isError && !data && isFetching && <Spinner />}
          {valid && !isError && data && feasibility && (
            <>
              <SimFeasibility
                feasibility={feasibility} current={current} goal={goal} semanas={debounced.weeks} simple={simple}
              />

              {!simple && season && !seasonFallo && <SimSeason season={season} />}

              {!simple && <SimCurveChart data={data} curve={debounced.curve} goal={goal} />}

              {!simple && <SimZones weeks={data.weeks} />}

              <Card
                title={`Plan semanal generado · ${data.weeks.length} semanas`}
                className="card-hover" animate={false} flush
                action={
                  <BotonPdf
                    label="Descargar PDF"
                    title="Descarga las tablas del simulador: zonas de entrenamiento, plan semana a semana y las semanas de extensión si las hay"
                    onClick={() => descargarSimPdf(debounced, data, simple)}
                  />
                }
              >
                <SimPlanTable weeks={data.weeks} simple={simple} />
                {!simple && (
                  <p className="border-t border-line px-4 py-2.5 text-[10px] text-text-faint">
                    Tiempo por zona: el punto medio de su rango, por 100 m.
                  </p>
                )}
              </Card>

              {/* Tabla de EXTENSIÓN: solo en modo completo */}
              {!simple && data.extension_weeks.length > 0 && (
                <SimExtensionTable
                  extensionWeeks={data.extension_weeks}
                  feasibility={feasibility}
                  weeks={debounced.weeks}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
