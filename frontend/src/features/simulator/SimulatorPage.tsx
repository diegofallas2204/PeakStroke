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
import { SIM_PARAMS_INICIALES } from './simDefaults'
import { SimParams } from './SimParams'
import { SimFeasibility } from './SimFeasibility'
import { SimSeason } from './SimSeason'
import { SimCurveChart } from './SimCurveChart'
import { SimPlanTable } from './SimPlanTable'
import { SimExtensionNotice, SimExtensionTable } from './SimExtension'
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
  const valid = current != null && goal != null && goal < current

  const { data, isFetching } = useQuery({
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
  const { data: season } = useQuery({
    queryKey: ['season', debounced.distance, debounced.stroke, current, debounced.pool],
    queryFn: () => api.simulator.season({
      distance: debounced.distance, stroke: debounced.stroke,
      current_time: current, pool: debounced.pool, n_macros: 3,
    }),
    enabled: current != null,
    placeholderData: (prev) => prev,
  })

  const [simple] = useSimpleMode()
  const ref = usePageEnter([])
  const feasibility = data?.feasibility

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Simulador de escenarios"
        subtitle="Modifica semanas, kilómetros y objetivos: el motor recalcula todo en tiempo real, sin tocar los planes guardados"
      />

      <div className="flex flex-col gap-4">
        {/* ── Parámetros (fila superior, a todo el ancho) ── */}
        <SimParams params={params} setParams={setParams} valid={valid} />

        {/* ── Resultados ── */}
        <div className="flex flex-col gap-4">
          {!data && isFetching && <Spinner />}
          {data && feasibility && (
            <>
              <SimFeasibility feasibility={feasibility} current={current} goal={goal} simple={simple} />

              {!simple && season && <SimSeason season={season} />}

              {/* Aviso de semanas extra: solo en modo completo */}
              {!simple && feasibility.recommended_weeks != null && (
                <SimExtensionNotice feasibility={feasibility} weeks={debounced.weeks} />
              )}

              {!simple && <SimCurveChart data={data} curve={debounced.curve} goal={goal} />}

              {!simple && <SimZones weeks={data.weeks} />}

              <Card title={`Plan semanal generado · ${data.weeks.length} semanas`} className="card-hover" animate={false} flush>
                <SimPlanTable weeks={data.weeks} simple={simple} />
                {!simple && (
                  <p className="border-t border-line px-4 py-2.5 text-[10px] text-text-faint">
                    Tiempo por zona = punto medio del rango (pace /100m sobre el tiempo esperado de la semana).
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
