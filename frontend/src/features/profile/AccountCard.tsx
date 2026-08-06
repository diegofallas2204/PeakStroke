// Tarjeta "Mi cuenta": la identidad de quien está usando la app.
import { KeyRound, Mail, UserRound } from 'lucide-react'
import type { Member } from '../../lib/types'
import { SECTION_ACCENT, roleMeta } from '../../lib/constants'
import { initials, toShortDate } from '../../lib/format'
import { Card, Chip } from '../../components/ui/primitives'

export function AccountCard({
  session, onChangePassword,
}: { session: Member; onChangePassword: () => void }) {
  const role = roleMeta(session.role, session.is_owner)
  const accent = SECTION_ACCENT['/perfil']

  return (
    <Card className="card-hover">
      <div className="flex flex-col items-center gap-3 pb-4 text-center">
        <div
          className="display flex size-16 items-center justify-center rounded-2xl text-[19px] font-bold"
          style={{ color: accent, background: `${accent}1a`, border: `1px solid ${accent}33` }}
        >
          {initials(session.name)}
        </div>
        <div className="min-w-0">
          <p className="display truncate text-[17px] font-bold leading-tight">{session.name}</p>
          <p className="mt-1 flex items-center justify-center gap-1.5 text-[11.5px] text-text-dim">
            <Mail size={11.5} className="shrink-0 text-text-faint" />
            <span className="truncate">{session.email}</span>
          </p>
        </div>
        <Chip color={role.color}>{role.label}</Chip>
      </div>

      <dl className="flex flex-col gap-2.5 border-t border-line pt-3.5 text-[11.5px]">
        <Row label="Equipo" value={session.team_name ?? '—'} dim={!session.team_name} />
        <Row label="Miembro desde" value={toShortDate(session.created_at)} />
        <Row
          label="Último acceso"
          value={session.last_login_at ? toShortDate(session.last_login_at) : 'Nunca'}
        />
        <Row
          label="Ficha deportiva"
          value={session.swimmer_name ?? 'Sin ligar'}
          dim={!session.swimmer_name}
        />
      </dl>

      <button className="btn btn-ghost mt-4 w-full justify-center" onClick={onChangePassword}>
        <KeyRound size={13.5} /> Cambiar contraseña
      </button>
    </Card>
  )
}

function Row({ label, value, dim = false }: { label: string; value: string; dim?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-text-faint">{label}</dt>
      <dd className={`truncate font-semibold ${dim ? 'text-text-faint' : 'text-text'}`}>{value}</dd>
    </div>
  )
}

/** Aviso de que la app está corriendo sin autenticación (solo en desarrollo). */
export function DevSessionNotice() {
  return (
    <Card className="!p-4">
      <div className="flex items-start gap-3">
        <span
          className="flex size-8 shrink-0 items-center justify-center rounded-lg"
          style={{ color: '#fbbf24', background: 'rgba(251,191,36,.12)', border: '1px solid rgba(251,191,36,.22)' }}
        >
          <UserRound size={15} strokeWidth={2.1} />
        </span>
        <div className="min-w-0">
          <p className="text-[12.5px] font-semibold">Sesión de desarrollo</p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-text-dim">
            La app no pide login todavía: todas las peticiones se atribuyen a esta cuenta y los
            permisos de rol no se aplican. Para probar el flujo real, arranca el backend con{' '}
            <code className="mono rounded bg-surface-2 px-1.5 py-0.5 text-[10.5px]">
              PEAKSTROKE_AUTH_ENABLED=true
            </code>
            .
          </p>
        </div>
      </div>
    </Card>
  )
}
