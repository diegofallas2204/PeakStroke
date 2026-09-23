// Base aeróbica: historial de tests por atleta + registro de nuevos tests
// (T-30, T-15, personalizado N×D, CSS 400/50 o ingreso directo).
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Timer, Plus, Trash2, TrendingDown, TrendingUp, Minus } from 'lucide-react'
import { api } from '../../lib/api'
import type { AerobicTest } from '../../lib/types'
import { TEST_TYPE_LABEL } from '../../lib/constants'
import { toClock } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { PageHeader } from '../../components/layout/PageHeader'
import { Card, EmptyState, Spinner } from '../../components/ui/primitives'
import { TestForm } from './TestForm'
import { SplitsChart } from './SplitsChart'
import { TrainingIntervalsCard } from './TrainingIntervalsCard'

const TREND_META = {
  improving: { label: 'En mejora', color: '#34d399', icon: TrendingDown },
  stable: { label: 'Estable', color: '#22d3ee', icon: Minus },
  declining: { label: 'Se cae', color: '#fb7185', icon: TrendingUp },
} as const

export function AerobicPage() {
  const [swimmerId, setSwimmerId] = useState<number | null>(null)
  const [selectedTest, setSelectedTest] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const queryClient = useQueryClient()

  const { data: swimmers } = useQuery({ queryKey: ['swimmers', ''], queryFn: () => api.swimmers.list() })
  const activeSwimmer = swimmerId ?? swimmers?.[0]?.id ?? null

  const { data: tests, isLoading } = useQuery({
    queryKey: ['aerobic', activeSwimmer],
    queryFn: () => api.aerobic.list(activeSwimmer!),
    enabled: activeSwimmer != null,
  })

  const test = useMemo(
    () => tests?.find((t) => t.id === selectedTest) ?? tests?.[0] ?? null,
    [tests, selectedTest],
  )

  const { data: previous } = useQuery({
    queryKey: ['aerobic-prev', test?.id],
    queryFn: () => api.aerobic.previous(test!.id),
    enabled: test != null && test.splits.length > 0,
  })

  const removeTest = useMutation({
    mutationFn: (id: number) => api.aerobic.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['aerobic'] }),
  })

  const ref = usePageEnter([activeSwimmer, isLoading])

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Base aeróbica"
        subtitle="T-30 / T-15, tests personalizados y CSS: el punto de partida del motor de predicción"
        actions={
          <>
            {/* El selector solo tiene sentido con varios nadadores entre los que
                elegir. A un atleta le sale un desplegable de una sola opción con
                su propio nombre, que es ruido. */}
            {(swimmers?.length ?? 0) > 1 && (
              <select
                className="field !w-52"
                value={activeSwimmer ?? ''}
                onChange={(e) => { setSwimmerId(Number(e.target.value)); setSelectedTest(null) }}
              >
                {swimmers?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            )}
            {/* Sin nadador no hay a quién registrarle el test: el backend lo
                rechazaría con un 404 que aquí se leería como un fallo. Es el
                caso del atleta cuya cuenta nadie ligó todavía a una ficha. */}
            {activeSwimmer != null && (
              <button className="btn btn-primary" onClick={() => setShowForm(true)}>
                <Plus size={14} /> Registrar test
              </button>
            )}
          </>
        }
      />

      {isLoading ? (
        <Spinner />
      ) : !tests?.length ? (
        <EmptyState
          icon={<Timer size={24} />}
          title={activeSwimmer == null ? 'Sin ficha deportiva' : 'Sin tests registrados'}
          hint={activeSwimmer == null
            ? 'Tu cuenta todavía no está ligada a un nadador, así que no hay a quién registrarle un test. Pídeselo a tu entrenador.'
            : 'Registra un T-30, T-15, un test personalizado (ej. 12×400) o un CSS para calcular la base aeróbica del atleta.'}
          action={activeSwimmer != null && (
            <button className="btn btn-primary" onClick={() => setShowForm(true)}>
              <Plus size={14} /> Registrar test
            </button>
          )}
        />
      ) : (
        <div className="grid grid-cols-[300px_1fr] items-start gap-4">
          <Card title="Historial de tests" className="card-hover self-start !p-2.5">
            <div className="flex flex-col gap-1.5">
              {tests.map((t) => {
                const trend = t.trend ? TREND_META[t.trend] : null
                const active = t.id === test?.id
                return (
                  <button
                    key={t.id}
                    onClick={() => setSelectedTest(t.id)}
                    className={`group flex items-center justify-between rounded-xl border px-3 py-2.5 text-left transition-all duration-200 ${
                      active ? 'border-[rgba(59,130,246,.45)] bg-[rgba(59,130,246,.1)]' : 'border-transparent hover:bg-surface-2'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[12px] font-bold">{TEST_TYPE_LABEL[t.test_type]}</span>
                        {t.test_type === 'CUSTOM' && t.rep_count && (
                          <span className="text-[10px] text-text-dim">{t.rep_count}×{t.rep_distance}</span>
                        )}
                      </div>
                      <p className="mt-0.5 text-[10px] text-text-faint">{t.test_date}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-right">
                        <p className="mono text-[12.5px] font-bold text-accent-soft">{toClock(t.avg_per100)}</p>
                        {trend && (
                          <p className="flex items-center justify-end gap-1 text-[9px]" style={{ color: trend.color }}>
                            <trend.icon size={9} /> {trend.label}
                          </p>
                        )}
                      </div>
                      <span
                        className="rounded-md p-1 text-text-faint opacity-0 transition-all hover:text-coral group-hover:opacity-100"
                        role="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (confirm('¿Eliminar este test?')) removeTest.mutate(t.id)
                        }}
                      >
                        <Trash2 size={11.5} />
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          </Card>

          {test && <TestDetail test={test} previous={previous ?? null} />}
        </div>
      )}

      <TestForm
        open={showForm}
        swimmerId={activeSwimmer}
        onClose={() => setShowForm(false)}
      />
    </div>
  )
}

function TestDetail({ test, previous }: { test: AerobicTest; previous: AerobicTest | null }) {
  const trend = test.trend ? TREND_META[test.trend] : null
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-4">
        <Card className="card-hover">
          <p className="card-title">Base aeróbica</p>
          <p className="display mt-1.5 text-[26px] font-bold text-accent-soft">{toClock(test.avg_per100)}</p>
          <p className="text-[10.5px] text-text-faint">por 100m</p>
        </Card>
        <Card className="card-hover">
          <p className="card-title">Consistencia (desv. est.)</p>
          <p className="display mt-1.5 text-[26px] font-bold text-cyan">
            {test.std_dev != null ? `±${test.std_dev.toFixed(2)}s` : '—'}
          </p>
          <p className="text-[10.5px] text-text-faint">
            {test.std_dev != null ? (test.std_dev < 1 ? 'Muy consistente' : test.std_dev < 2 ? 'Consistente' : 'Variable') : 'Sin parciales'}
          </p>
        </Card>
        {/* La salida ocupa el sitio de la tendencia cuando el test la registró:
            es el dato nuevo y el que gobierna la prescripción. La tendencia baja
            a la gráfica de parciales, donde ya se ve dibujada. */}
        {test.send_off != null ? (
          <Card className="card-hover">
            <p className="card-title">Salida · descanso</p>
            <p className="display mt-1.5 text-[26px] font-bold text-mint">
              {toClock(test.send_off, 0)}
            </p>
            <p className="text-[10.5px] text-text-faint">
              {test.avg_rest != null && <>{test.avg_rest.toFixed(1)}s de descanso medio</>}
              {test.density != null && <> · {(test.density * 100).toFixed(0)}% de densidad</>}
            </p>
          </Card>
        ) : (
        <Card className="card-hover">
          <p className="card-title">Tendencia del test</p>
          {trend ? (
            <>
              <p className="display mt-1.5 flex items-center gap-2 text-[22px] font-bold" style={{ color: trend.color }}>
                <trend.icon size={20} /> {trend.label}
              </p>
              <p className="text-[10.5px] text-text-faint">A lo largo de las repeticiones</p>
            </>
          ) : test.css_ms != null ? (
            <>
              <p className="display mt-1.5 text-[26px] font-bold text-mint">{test.css_ms.toFixed(2)} m/s</p>
              <p className="text-[10.5px] text-text-faint">Critical Swim Speed</p>
            </>
          ) : (
            <p className="display mt-1.5 text-[26px] font-bold text-text-faint">—</p>
          )}
        </Card>
        )}
      </div>

      {/* La tendencia se pierde de las tarjetas cuando la salida ocupa su sitio;
          aquí sigue disponible y además dibujada. */}
      {test.send_off != null && trend && (
        <p className="-mt-1 flex items-center gap-1.5 text-[11px]" style={{ color: trend.color }}>
          <trend.icon size={12} /> {trend.label} a lo largo de las repeticiones
          {test.missed_intervals.length > 0 && (
            <span className="text-amber">
              · no llegó a la salida en {test.missed_intervals.length}{' '}
              {test.missed_intervals.length === 1 ? 'repetición' : 'repeticiones'}
            </span>
          )}
        </p>
      )}

      <TrainingIntervalsCard testId={test.id} />

      {test.per100_splits.length > 0 ? (
        <Card
          title={
            previous
              ? `Parciales /100m · comparado con ${TEST_TYPE_LABEL[previous.test_type]} (${previous.test_date})`
              : 'Parciales /100m'
          }
          className="card-hover"
        >
          <SplitsChart test={test} previous={previous} />
        </Card>
      ) : (
        <Card title="Detalle" className="card-hover">
          <p className="text-xs text-text-dim">
            {test.test_type === 'CSS'
              ? 'Test CSS calculado con la fórmula de Wakayoshi: 350 / (T400 − T50). El T-pace resultante es la referencia de umbral del atleta.'
              : 'Base aeróbica ingresada directamente por el entrenador.'}
          </p>
          {test.notes && <p className="mt-2 text-xs text-text-faint">{test.notes}</p>}
        </Card>
      )}
    </div>
  )
}
