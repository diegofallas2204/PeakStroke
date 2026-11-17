// Entrenamiento: lo que el atleta nadó cada día (C7) y la carga que sale de ahí
// (C8, Banister). De los dos roles: el atleta apunta lo suyo y el entrenador lo
// ve —y lo corrige— en cada uno de sus atletas. El backend acota los datos; esta
// página no decide nada de permisos.
//
// `?nueva=1` abre el formulario directamente: es el «Apuntar sesión» del inicio
// del atleta, para que apuntar después de nadar sean dos toques. `?atleta=<id>`
// llega desde la tabla del equipo y elige a ese atleta.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Activity, Plus } from 'lucide-react'
import { api } from '../../lib/api'
import type { TrainingSession } from '../../lib/types'
import { SECTION_ACCENT } from '../../lib/constants'
import { isoDay } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { useIsCoach } from '../../hooks/useSession'
import { PageHeader } from '../../components/layout/PageHeader'
import { EmptyState, Segmented, Spinner } from '../../components/ui/primitives'
import { ErrorDeCarga } from '../../components/ui/ErrorDeCarga'
import { SessionForm } from './SessionForm'
import { SessionsCard } from './SessionsCard'
import { LoadCard } from './LoadCard'

type Rango = '30' | '90' | '180' | '365'
const RANGOS: { value: Rango; label: string }[] = [
  { value: '30', label: '30 d' },
  { value: '90', label: '90 d' },
  { value: '180', label: '6 m' },
  { value: '365', label: '1 año' },
]

function rangoDeFechas(dias: number): { desde: string; hasta: string } {
  const hoy = new Date()
  const desde = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() - dias + 1)
  return { desde: isoDay(desde), hasta: isoDay(hoy) }
}

export function TrainingPage() {
  const [params, setParams] = useSearchParams()
  const pideNueva = params.get('nueva') === '1'
  const pedido = Number(params.get('atleta')) || null
  const [swimmerId, setSwimmerId] = useState<number | null>(pedido)
  const [rango, setRango] = useState<Rango>('90')
  const [form, setForm] = useState<{ open: boolean; session: TrainingSession | null }>(
    { open: pideNueva, session: null },
  )

  const atletasQ = useQuery({
    queryKey: ['swimmers', ''], queryFn: () => api.swimmers.list(),
  })
  const { data: swimmers, isLoading: loadingSwimmers } = atletasQ
  // El pedido por URL solo vale si está en la lista (que ya viene acotada): un
  // id ajeno o dado de baja cae al primero, no a una pantalla de 404.
  const elegido = swimmers?.some((s) => s.id === swimmerId) ? swimmerId : null
  const activeSwimmer = elegido ?? swimmers?.[0]?.id ?? null
  const { desde, hasta } = rangoDeFechas(Number(rango))

  const sesionesQ = useQuery({
    queryKey: ['sessions', activeSwimmer, desde, hasta],
    queryFn: () => api.sessions.list(activeSwimmer!, desde, hasta),
    enabled: activeSwimmer != null,
  })
  const { data: sessions, isLoading: loadingSessions } = sesionesQ
  const cargaQ = useQuery({
    queryKey: ['training-load', activeSwimmer, desde, hasta],
    queryFn: () => api.trainingLoad.get(activeSwimmer!, desde, hasta),
    enabled: activeSwimmer != null,
  })
  const { data: load, isLoading: loadingLoad } = cargaQ
  // Un fallo no es «sin atletas» ni «sin sesiones»: se dice y se puede reintentar.
  const fallo = [
    { q: atletasQ, que: 'los atletas' },
    { q: sesionesQ, que: 'las sesiones' },
    { q: cargaQ, que: 'la carga' },
  ].find(({ q }) => q.isError)

  const ref = usePageEnter([activeSwimmer, loadingSessions, loadingLoad])

  const abrirNueva = () => setForm({ open: true, session: null })
  const cerrar = () => {
    setForm({ open: false, session: null })
    // Que recargar la página no vuelva a abrir el formulario.
    if (pideNueva) setParams({}, { replace: true })
  }

  const isCoach = useIsCoach()
  const cargando = loadingSwimmers || (activeSwimmer != null && (loadingSessions || loadingLoad))

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Entrenamiento"
        subtitle="Lo que se nadó cada día y la carga que acumula: CTL, ATL y TSB con sus avisos"
        actions={
          <>
            {/* Como en Base aeróbica: a un atleta, un desplegable con su propio
                nombre como única opción es ruido. */}
            {(swimmers?.length ?? 0) > 1 && (
              <select
                className="field !w-52" aria-label="Atleta"
                value={activeSwimmer ?? ''}
                onChange={(e) => setSwimmerId(Number(e.target.value))}
              >
                {swimmers?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            )}
            <Segmented value={rango} options={RANGOS} onChange={setRango} label="Rango" accent={SECTION_ACCENT['/entrenamiento']} />
            {activeSwimmer != null && (
              <button className="btn btn-primary" onClick={abrirNueva}>
                <Plus size={14} /> Apuntar sesión
              </button>
            )}
          </>
        }
      />

      {cargando ? (
        <Spinner />
      ) : fallo ? (
        <ErrorDeCarga
          error={fallo.q.error} que={fallo.que}
          onReintentar={() => void fallo.q.refetch()} reintentando={fallo.q.isFetching}
        />
      ) : activeSwimmer == null ? (
        // Sin nadador no hay a quién apuntarle nada (el backend daría 404). Al
        // atleta le pasa si nadie ligó su cuenta a una ficha; al entrenador, si
        // el club aún no tiene atletas.
        isCoach ? (
          <EmptyState
            icon={<Activity size={24} />}
            title="Sin atletas"
            hint="Da de alta a tus atletas en la sección Atletas para apuntarles sesiones."
          />
        ) : (
          <EmptyState
            icon={<Activity size={24} />}
            title="Sin ficha deportiva"
            hint="Tu cuenta todavía no está ligada a un nadador, así que no hay a quién apuntarle sesiones. Pídeselo a tu entrenador."
          />
        )
      ) : (
        <>
          {load && <LoadCard load={load} />}
          <SessionsCard
            sessions={sessions ?? []}
            onNew={abrirNueva}
            onEdit={(s) => setForm({ open: true, session: s })}
          />
        </>
      )}

      <SessionForm
        // Con `?nueva=1` y sin ficha, el formulario no se abre: no habría a
        // quién guardarle la sesión y el error del guardado confundiría.
        open={form.open && activeSwimmer != null}
        swimmerId={activeSwimmer}
        session={form.session}
        onClose={cerrar}
      />
    </div>
  )
}
