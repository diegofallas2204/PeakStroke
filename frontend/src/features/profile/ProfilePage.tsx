// Perfil: quién soy y —si soy entrenador— a quién administro.
// Deliberadamente separada de Ajustes (tema, modo simplificado): identidad y
// apariencia son cosas distintas.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { UserX } from 'lucide-react'
import { api } from '../../lib/api'
import { usePageEnter } from '../../hooks/usePageEnter'
import { useAuthConfig, useIsCoach, useSession, useSinEquipo } from '../../hooks/useSession'
import { PageHeader } from '../../components/layout/PageHeader'
import { EmptyState, Spinner } from '../../components/ui/primitives'
import { AccountCard, DevSessionNotice } from './AccountCard'
import { AthleteProfileCard } from './AthleteProfileCard'
import { MembersCard } from './MembersCard'
import { MemberForm } from './MemberForm'
import { JoinRequestsCard } from './JoinRequestsCard'
import { PasswordForm } from './PasswordForm'
import { TeamCard } from './TeamCard'

export function ProfilePage() {
  const { data: session, isLoading, isError } = useSession()
  const { data: authConfig } = useAuthConfig()
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [memberOpen, setMemberOpen] = useState(false)

  // Del hook y no calculado aquí: el mismo `role === 'coach'` estaba escrito a
  // mano en cuatro sitios, que es como se acaba con cuatro versiones que se
  // parecen. `useIsOwner` vive al lado para la capa de dueño.
  const isCoach = useIsCoach()
  // Cuenta que existe y todavía no está en ningún club: su perfil es lo único
  // que puede ver, y lo único accionable ahí son sus solicitudes de ingreso.
  const sinEquipo = useSinEquipo()
  const { data: members, isLoading: loadingMembers } = useQuery({
    queryKey: ['members'],
    queryFn: () => api.auth.members(),
    enabled: isCoach,
  })
  const { data: team } = useQuery({
    queryKey: ['team'],
    queryFn: () => api.teams.mine(),
    enabled: isCoach,
  })

  const ref = usePageEnter([isLoading, isCoach, loadingMembers])

  if (isLoading) return <Spinner />
  if (isError || !session) {
    return (
      <EmptyState
        icon={<UserX size={24} />}
        title="Sin sesión activa"
        hint="No se pudo identificar al usuario. Comprueba que el backend esté corriendo."
      />
    )
  }

  return (
    <div ref={ref} className="flex flex-col gap-5">
      <PageHeader
        title="Perfil"
        subtitle={
          isCoach
            ? 'Tu cuenta y los accesos del equipo'
            : sinEquipo
              ? 'Tu cuenta y tus solicitudes de ingreso a un equipo'
              : 'Tu cuenta y tu ficha deportiva'
        }
      />

      {authConfig && !authConfig.auth_enabled && <DevSessionNotice />}

      {/* La columna de la cuenta se queda fija y estrecha; el contenido que
          crece (la tabla del equipo) se lleva el espacio sobrante.
          `[&>*]:min-w-0` es imprescindible: por defecto un hijo de grid tiene
          min-width:auto y la tabla de miembros (celdas con nowrap) estiraría la
          columna más allá del viewport en móvil. */}
      <div className="grid items-start gap-4 [&>*]:min-w-0 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
        {/* Columna izquierda: quién soy y, si administro, qué club. */}
        <div className="flex flex-col gap-4">
          <AccountCard session={session} onChangePassword={() => setPasswordOpen(true)} />
          {isCoach && team && <TeamCard team={team} members={members ?? []} />}
        </div>

        {isCoach ? (
          loadingMembers ? (
            <Spinner />
          ) : (
            <MembersCard
              members={members ?? []}
              currentId={session.id}
              onInvite={() => setMemberOpen(true)}
            />
          )
        ) : session.swimmer_id == null ? (
          // Sin ficha no hay nada que enseñar todavía: lo único accionable son
          // las solicitudes de ingreso, así que ocupan el sitio de la ficha en
          // vez de sumarse debajo de un estado vacío que dice lo mismo. Cubre a
          // la vez al invitado sin club y al atleta del club que aún no canjeó.
          <JoinRequestsCard />
        ) : (
          <AthleteProfileCard swimmerId={session.swimmer_id} />
        )}
      </div>

      <PasswordForm open={passwordOpen} onClose={() => setPasswordOpen(false)} />
      {isCoach && <MemberForm open={memberOpen} onClose={() => setMemberOpen(false)} />}
    </div>
  )
}
