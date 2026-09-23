// Solicitudes de ingreso a un equipo, del lado del atleta.
//
// Sustituye a la antigua "Vincular mi ficha", que solo tenía la caja del código.
// Faltaba la mitad de arriba: **de quién es la invitación**. Un código a secas
// pide teclear ocho caracteres sin decir a qué club te metes ni quién te llamó,
// y quien recibe dos —cambia de club a mitad de temporada— no tenía forma de
// saber cuál estaba canjeando.
//
// **La lista no trae el código, a propósito.** Teclearlo es la prueba de que
// quien acepta es la persona que el entrenador invitó; enseñarlo aquí, a alguien
// ya autenticado con ese correo, lo dejaría en un botón y el segundo factor
// desaparecería.
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Inbox, KeyRound, Users } from 'lucide-react'
import { api } from '../../lib/api'
import { toShortDate } from '../../lib/format'
import { Card } from '../../components/ui/primitives'

export function JoinRequestsCard() {
  const [code, setCode] = useState('')
  const queryClient = useQueryClient()

  const { data: solicitudes, isLoading } = useQuery({
    queryKey: ['join-requests'],
    queryFn: () => api.linkCodes.mine(),
  })

  const canjear = useMutation({
    mutationFn: () => api.linkCodes.redeem(code),
    onSuccess: () => {
      // La sesión cambia de forma: gana equipo, rol y `swimmer_id`, y de ahí
      // cuelga todo lo que el atleta ve. Se invalida entera en vez de parchearla.
      queryClient.invalidateQueries()
      setCode('')
    },
  })

  return (
    <Card title="Solicitudes de ingreso">
      {isLoading ? null : solicitudes?.length ? (
        <ul className="mb-4 flex flex-col gap-2">
          {solicitudes.map((s, i) => (
            <li
              key={`${s.team_name}-${i}`}
              className="flex items-start gap-3 rounded-xl border border-line bg-surface-2 px-3.5 py-3"
            >
              <Users size={15} className="mt-0.5 shrink-0 text-accent-soft" />
              <div className="min-w-0 flex-1">
                <p className="text-[12.5px] font-semibold leading-tight">{s.team_name}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-text-dim">
                  Te invitaron como <span className="font-semibold text-text">{s.swimmer_name}</span>
                  {s.invited_by && <> · {s.invited_by}</>}
                </p>
              </div>
              <span className="shrink-0 text-[10.5px] text-text-faint">
                vence {toShortDate(s.expires_at)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mb-4 flex items-start gap-3 text-[12.5px] leading-relaxed text-text-dim">
          <Inbox size={16} className="mt-0.5 shrink-0 text-text-faint" />
          <p>
            No tienes solicitudes pendientes. Cuando un entrenador te dé de alta
            con tu correo, la invitación aparece aquí.
          </p>
        </div>
      )}

      <p className="text-[12.5px] leading-relaxed text-text-dim">
        {solicitudes?.length
          ? 'Escribe el código que te dio tu entrenador para confirmar que eres tú.'
          : 'Si ya tienes un código de vinculación, puedes canjearlo aquí.'}
      </p>

      <form
        className="mt-3 flex flex-wrap items-center gap-2.5"
        onSubmit={(e) => { e.preventDefault(); if (code.trim()) canjear.mutate() }}
      >
        <input
          className="field mono !w-44 text-center !tracking-[0.16em]"
          placeholder="ABCD-2345"
          value={code}
          // En mayúsculas según se teclea: el código lo es, y ver algo distinto
          // de lo que se dictó hace dudar de si se escribió bien.
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          maxLength={20}
          aria-label="Código de vinculación"
        />
        <button className="btn btn-primary" disabled={!code.trim() || canjear.isPending}>
          <KeyRound size={13.5} /> {canjear.isPending ? 'Canjeando…' : 'Aceptar invitación'}
        </button>
      </form>

      {canjear.isError && (
        <p className="mt-3 text-[11.5px] text-coral">{(canjear.error as Error).message}</p>
      )}
      {canjear.isSuccess && (
        <p className="mt-3 text-[11.5px] text-mint">
          Listo: ya eres parte de {canjear.data.team_name} como {canjear.data.swimmer_name}.
        </p>
      )}
    </Card>
  )
}
