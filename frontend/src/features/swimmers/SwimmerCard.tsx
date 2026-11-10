// Una ficha del equipo, con su estado de acceso.
//
// El estado de acceso vive aquí y no en la sección Perfil porque ficha y cuenta
// son la misma persona: tener dos listas —«atletas» y «miembros»— obligaba a
// cruzarlas a ojo para responder «¿este ya puede entrar?». La lista de atletas
// es ahora el pool completo y dice de cada uno en cuál de los tres estados está.
import { Pencil, UserMinus, KeyRound, MailCheck, Ruler, Weight } from 'lucide-react'
import type { LinkCode, Swimmer } from '../../lib/types'
import { SPECIALTY_LABEL, STROKE_LABEL } from '../../lib/constants'
import { initials } from '../../lib/format'
import { Card, Chip, IconButton } from '../../components/ui/primitives'

const SPECIALTY_COLOR: Record<string, string> = {
  velocidad: '#fb7185', medio_fondo: '#3b82f6', fondo: '#22d3ee', aguas_abiertas: '#34d399',
}

export function SwimmerCard({
  swimmer, code, onEdit, onDeactivate, onManageAccess,
}: {
  swimmer: Swimmer
  /** Su código vivo, si tiene uno emitido y sin canjear. */
  code: LinkCode | undefined
  onEdit: () => void
  onDeactivate: () => void
  onManageAccess: () => void
}) {
  const color = SPECIALTY_COLOR[swimmer.specialty] ?? '#3b82f6'

  return (
    <Card className="card-hover group">
      <div className="flex items-start gap-3.5">
        <div
          className="display flex size-11 shrink-0 items-center justify-center rounded-xl text-[13px] font-bold"
          style={{ color, background: `${color}1a`, border: `1px solid ${color}33` }}
        >
          {initials(swimmer.name)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-semibold">{swimmer.name}</p>
          <p className="mt-0.5 text-[11px] text-text-dim">
            {swimmer.age != null ? `${swimmer.age} años` : 'Edad —'}
            {swimmer.gender ? ` · ${swimmer.gender}` : ''}
          </p>
        </div>
        <div className="reveal flex gap-1">
          <IconButton label={`Editar ${swimmer.name}`} onClick={onEdit} className="!size-8">
            <Pencil size={13} />
          </IconButton>
          <IconButton label={`Dar de baja a ${swimmer.name}`} tone="danger" onClick={onDeactivate} className="!size-8">
            <UserMinus size={13} />
          </IconButton>
        </div>
      </div>

      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        <Chip color={color}>{SPECIALTY_LABEL[swimmer.specialty]}</Chip>
        <Chip color="#8b93b8">{STROKE_LABEL[swimmer.main_stroke]}</Chip>
      </div>

      <Acceso swimmer={swimmer} code={code} onManageAccess={onManageAccess} />

      <div className="mt-3 flex gap-4 border-t border-line pt-3 text-[11px] text-text-dim">
        <span className="flex items-center gap-1.5">
          <Weight size={11.5} className="text-text-faint" />
          {swimmer.weight_kg ? `${swimmer.weight_kg} kg` : '—'}
        </span>
        <span className="flex items-center gap-1.5">
          <Ruler size={11.5} className="text-text-faint" />
          {swimmer.height_cm ? `${swimmer.height_cm} cm` : '—'}
        </span>
      </div>
    </Card>
  )
}

/** Los tres estados posibles del vínculo, y la acción que lleva al siguiente. */
function Acceso({
  swimmer, code, onManageAccess,
}: { swimmer: Swimmer; code: LinkCode | undefined; onManageAccess: () => void }) {
  if (swimmer.user_email) {
    return (
      <div className="mt-3 flex items-center gap-2 border-t border-line pt-3 text-[11px]">
        <MailCheck size={12.5} className="shrink-0 text-mint" />
        <span className="truncate text-text-dim" title={swimmer.user_email}>
          {swimmer.user_email}
        </span>
      </div>
    )
  }

  return (
    <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-3">
      {code ? (
        <span className="mono text-[12px] font-bold tracking-[0.12em] text-amber">
          {code.code}
        </span>
      ) : (
        <span className="text-[11px] text-text-faint">Sin cuenta</span>
      )}
      {/* «Sin cuenta» (o el código) ya está escrito al lado: la llave no
          necesita repetirlo. */}
      <IconButton
        label={code ? `Ver el código de ${swimmer.name}` : `Dar acceso a ${swimmer.name}`}
        onClick={onManageAccess}
        className="!size-8"
      >
        <KeyRound size={13} />
      </IconButton>
    </div>
  )
}
