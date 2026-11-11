// Los tres bloques de la página del atleta. Cada uno es un resumen de una
// sección y un enlace a ella ya filtrada por ese atleta (`?atleta=<id>`).
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowUpRight, type LucideIcon } from 'lucide-react'
import { api } from '../../lib/api'
import { LOAD_ALERT_META, PLAN_STATUS_META, STROKE_LABEL, TEST_TYPE_LABEL } from '../../lib/constants'
import { toClock, toShortDate } from '../../lib/format'
import { NAV_ITEMS } from '../../components/layout/navConfig'
import { enlace } from '../../lib/modulos'
import { Chip, Spinner } from '../../components/ui/primitives'

/** Un bloque: el color y el icono de su sección, y toda la tarjeta es el enlace. */
function Bloque({
  seccion, a, titulo, cargando, children,
}: { seccion: string; a: string; titulo: string; cargando: boolean; children: ReactNode }) {
  const item = NAV_ITEMS.find((i) => i.to === seccion)
  const color = item?.color ?? 'var(--color-accent)'
  const Icono: LucideIcon | undefined = item?.icon
  // Si esta build no trae esa sección (`lib/modulos.ts`), el resumen se queda
  // y deja de ser un enlace.
  const destino = enlace(a)
  const cuerpo = (
    <>
      <div className="mb-3 flex items-center gap-2">
        {Icono && (
          <span
            className="flex size-7 items-center justify-center rounded-lg"
            style={{ color, background: `${color}1c` }}
          >
            <Icono size={14} />
          </span>
        )}
        <span className="card-title flex-1">{titulo}</span>
        {destino && (
          <ArrowUpRight
            size={14}
            className="text-text-faint transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
            style={{ color }}
            aria-hidden
          />
        )}
      </div>
      {cargando ? <Spinner /> : children}
    </>
  )
  const estilo = { '--page-accent': color } as React.CSSProperties
  return destino ? (
    <Link to={destino} className="card card-hover group flex flex-col p-5" style={estilo} data-animate>
      {cuerpo}
    </Link>
  ) : (
    <div className="card flex flex-col p-5" style={estilo} data-animate>{cuerpo}</div>
  )
}

function Vacio({ children }: { children: ReactNode }) {
  return <p className="text-[12px] text-text-faint">{children}</p>
}

export function BloqueMacrociclo({ swimmerId }: { swimmerId: number }) {
  const { data: planes, isLoading } = useQuery({ queryKey: ['plans'], queryFn: api.plans.list })
  // Un atleta, un macrociclo vivo: si hay varios, el activo; si no, el último.
  const suyos = (planes ?? []).filter((p) => p.athletes.some((a) => a.swimmer_id === swimmerId))
  const plan = suyos.find((p) => p.effective_status === 'active') ?? suyos[0]
  const inscripcion = plan?.athletes.find((a) => a.swimmer_id === swimmerId)
  const estado = plan ? PLAN_STATUS_META[plan.effective_status] ?? PLAN_STATUS_META.draft : null

  return (
    <Bloque
      seccion="/plan-semanal" a={`/plan-semanal?atleta=${swimmerId}`}
      titulo="Plan semanal" cargando={isLoading}
    >
      {!plan || !inscripcion ? (
        <Vacio>No está en ningún macrociclo.</Vacio>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <p className="display truncate text-[15px] font-bold">{plan.name}</p>
            {estado && <Chip color={estado.color}>{estado.label}</Chip>}
          </div>
          {plan.current_week && (
            <p className="mt-0.5 text-[11.5px] text-text-dim">
              Semana {plan.current_week} de {plan.total_weeks}
            </p>
          )}
          <ul className="mt-3 flex flex-col gap-1.5">
            {inscripcion.events.map((ev) => (
              <li key={ev.id} className="flex items-baseline justify-between gap-3 text-[12px]">
                <span className="text-text-dim">{ev.distance}m {STROKE_LABEL[ev.stroke] ?? ev.stroke}</span>
                <span className="mono">
                  {toClock(ev.current_time)} <span className="text-text-faint">→</span>{' '}
                  <span className="font-semibold text-mint">{toClock(ev.goal_time)}</span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Bloque>
  )
}

export function BloqueTest({ swimmerId }: { swimmerId: number }) {
  const { data: tests, isLoading } = useQuery({
    queryKey: ['aerobic', swimmerId], queryFn: () => api.aerobic.list(swimmerId),
  })
  const ultimo = tests?.[0]
  return (
    <Bloque seccion="/pruebas" a={`/pruebas?atleta=${swimmerId}`} titulo="Base aeróbica" cargando={isLoading}>
      {!ultimo ? (
        <Vacio>Sin tests registrados.</Vacio>
      ) : (
        <>
          <p className="display text-[26px] font-bold leading-none text-accent-soft">
            {toClock(ultimo.avg_per100)}
            <span className="ml-1.5 text-[12px] font-semibold text-text-dim">/100m</span>
          </p>
          <p className="mt-2 text-[11.5px] text-text-dim">
            {TEST_TYPE_LABEL[ultimo.test_type] ?? ultimo.test_type} · {toShortDate(ultimo.test_date)}
            {tests && tests.length > 1 && <> · {tests.length} tests</>}
          </p>
        </>
      )}
    </Bloque>
  )
}

export function BloqueCarga({ swimmerId }: { swimmerId: number }) {
  const { data: carga, isLoading } = useQuery({
    queryKey: ['training-load', swimmerId, 'resumen'],
    queryFn: () => api.trainingLoad.get(swimmerId),
  })
  const hoy = carga?.days.at(-1)
  const aviso = hoy?.alert ? LOAD_ALERT_META[hoy.alert] : null
  return (
    <Bloque
      seccion="/entrenamiento" a={`/entrenamiento?atleta=${swimmerId}`}
      titulo="Forma (TSB)" cargando={isLoading}
    >
      {!hoy ? (
        <Vacio>Sin sesiones con carga todavía.</Vacio>
      ) : (
        <>
          <p
            className="display text-[26px] font-bold leading-none"
            style={{ color: hoy.tsb >= 0 ? 'var(--color-mint)' : 'var(--color-coral)' }}
          >
            {hoy.tsb > 0 ? '+' : ''}{hoy.tsb.toFixed(1)}
          </p>
          <p className="mt-2 text-[11.5px] text-text-dim">
            CTL {hoy.ctl.toFixed(1)} · ATL {hoy.atl.toFixed(1)}
          </p>
          {aviso && (
            <p className="mt-1.5 text-[11.5px] font-semibold" style={{ color: aviso.color }}>{aviso.label} hoy</p>
          )}
        </>
      )}
    </Bloque>
  )
}
