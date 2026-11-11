// La página de un atleta (`/atletas/:id`): todo lo suyo en un sitio, y desde
// aquí a cada sección ya filtrada por él.
//
// Hasta el 2026-11-10 la tarjeta del pool solo crecía al pasar el ratón: no
// llevaba a ningún lado, y ver el plan de un atleta era ir a Plan semanal y
// buscarlo en el selector. Esta página no tiene datos propios ni endpoint
// nuevo: lee lo que ya sirven la ficha, los macrociclos, los tests y la carga,
// todos acotados por el backend como siempre — un id ajeno es un 404.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, KeyRound, MailCheck, Pencil, UserX } from 'lucide-react'
import { api } from '../../lib/api'
import { SPECIALTY_COLOR, SPECIALTY_LABEL, STROKE_LABEL } from '../../lib/constants'
import { initials } from '../../lib/format'
import { usePageEnter } from '../../hooks/usePageEnter'
import { Card, Chip, EmptyState, IconButton, Spinner } from '../../components/ui/primitives'
import { SwimmerForm } from './SwimmerForm'
import { LinkCodeModal } from './LinkCodeModal'
import { BloqueCarga, BloqueMacrociclo, BloqueTest } from './AtletaBloques'

export function AtletaPage() {
  const id = Number(useParams().id)
  const [editando, setEditando] = useState(false)
  const [acceso, setAcceso] = useState(false)

  const { data: atleta, isLoading, isError } = useQuery({
    queryKey: ['swimmer', id],
    queryFn: () => api.swimmers.getOne(id),
    enabled: Number.isFinite(id),
    retry: false,
  })
  const { data: codigos } = useQuery({ queryKey: ['link-codes'], queryFn: api.linkCodes.list })
  const codigo = codigos?.find((c) => c.swimmer_id === id) ?? null

  const ref = usePageEnter([isLoading, atleta?.id])

  if (isLoading) return <Spinner />
  if (isError || !atleta) {
    return (
      <EmptyState
        icon={<UserX size={24} />}
        title="Atleta no encontrado"
        hint="Puede que lo hayan dado de baja o que no sea de tu equipo."
        action={<Link to="/atletas" className="btn btn-primary"><ArrowLeft size={14} /> Atletas</Link>}
      />
    )
  }

  const color = SPECIALTY_COLOR[atleta.specialty] ?? '#3b82f6'
  const datos = [
    atleta.age != null ? `${atleta.age} años` : null,
    atleta.gender,
    atleta.weight_kg ? `${atleta.weight_kg} kg` : null,
    atleta.height_cm ? `${atleta.height_cm} cm` : null,
  ].filter(Boolean).join(' · ')

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-3" data-animate>
        <Link
          to="/atletas" className="btn btn-ghost btn-icon"
          aria-label="Volver a Atletas" title="Volver a Atletas"
        >
          <ArrowLeft size={15} />
        </Link>
        <div
          className="display flex size-14 shrink-0 items-center justify-center rounded-2xl text-[17px] font-bold"
          style={{ color, background: `${color}1a`, border: `1px solid ${color}33` }}
        >
          {initials(atleta.name)}
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="display truncate text-[24px] font-bold leading-tight tracking-[-0.02em]">
            {atleta.name}
          </h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <Chip color={color}>{SPECIALTY_LABEL[atleta.specialty] ?? atleta.specialty}</Chip>
            <Chip color="#8b93b8">{STROKE_LABEL[atleta.main_stroke] ?? atleta.main_stroke}</Chip>
            {!atleta.is_active && <Chip color="#fb7185">De baja</Chip>}
            {datos && <span className="text-[12px] text-text-dim">{datos}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {atleta.user_email ? (
            <span
              className="flex max-w-56 items-center gap-1.5 truncate text-[11.5px] text-text-dim"
              title={`Entra con ${atleta.user_email}`}
            >
              <MailCheck size={13} className="shrink-0 text-mint" />
              <span className="truncate">{atleta.user_email}</span>
            </span>
          ) : (
            <IconButton
              label={codigo ? `Ver el código de ${atleta.name}` : `Dar acceso a ${atleta.name}`}
              onClick={() => setAcceso(true)}
            >
              <KeyRound size={14} />
            </IconButton>
          )}
          <IconButton label={`Editar ${atleta.name}`} onClick={() => setEditando(true)}>
            <Pencil size={14} />
          </IconButton>
        </div>
      </header>

      <div className="grid gap-4 [&>*]:min-w-0 lg:grid-cols-3">
        <BloqueMacrociclo swimmerId={atleta.id} />
        <BloqueTest swimmerId={atleta.id} />
        <BloqueCarga swimmerId={atleta.id} />
      </div>

      {atleta.notes && (
        <Card title="Notas">
          <p className="whitespace-pre-line text-[12.5px] leading-relaxed text-text-dim">{atleta.notes}</p>
        </Card>
      )}

      <SwimmerForm open={editando} swimmer={atleta} onClose={() => setEditando(false)} />
      <LinkCodeModal swimmer={acceso ? atleta : null} code={codigo} onClose={() => setAcceso(false)} />
    </div>
  )
}
