// Alta de un ENTRENADOR desde Perfil.
//
// **Ya no da de alta atletas.** Hasta el 2026-08-10 este formulario tenía un
// desplegable de rol, y con él la aplicación tenía dos formas de meter a un
// atleta: esta —que creaba una cuenta suelta, sin ficha— y la de Atletas, que
// creaba una ficha suelta, sin cuenta. Ficha y cuenta siempre fueron la misma
// persona, así que lo que producían las dos era media persona cada una, y unirlas
// después era un tercer paso que había que acordarse de dar.
//
// El atleta entra ahora por un solo sitio: «Agregar atleta» en Atletas, que crea
// ficha + cuenta + código de una vez (`features/swimmers/InviteAthleteModal`).
// Aquí se quedó lo que de verdad es distinto: un entrenador no tiene ficha
// deportiva, así que su alta nunca fue el mismo gesto.
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, UserPlus } from 'lucide-react'
import { api } from '../../lib/api'
import type { MemberCreated } from '../../lib/types'
import { Field, Modal } from '../../components/ui/primitives'

const EMPTY = { name: '', email: '', password: '' }

export function MemberForm({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form, setForm] = useState(EMPTY)
  const [created, setCreated] = useState<MemberCreated | null>(null)
  const queryClient = useQueryClient()

  // Al abrir se limpia el formulario. Ajuste de estado durante el render
  // (patrón oficial de React) en vez de efecto — igual que SwimmerForm.
  const [prevOpen, setPrevOpen] = useState(open)
  if (prevOpen !== open) {
    setPrevOpen(open)
    if (open) { setForm(EMPTY); setCreated(null) }
  }

  const mutation = useMutation({
    mutationFn: () => api.auth.createMember({
      email: form.email.trim(),
      name: form.name.trim(),
      // Fijo, no elegible: los atletas entran por «Agregar atleta».
      role: 'coach',
      password: form.password ? form.password : null,
    }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['members'] })
      queryClient.invalidateQueries({ queryKey: ['swimmers'] })
      // Si el backend generó la contraseña hay que enseñarla antes de cerrar:
      // es la única vez que se puede leer.
      if (data.temporary_password) setCreated(data)
      else onClose()
    },
  })

  const valid = form.name.trim().length >= 2 && /.+@.+\..+/.test(form.email) &&
    (!form.password || form.password.length >= 8)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={created ? 'Entrenador agregado' : 'Agregar entrenador'}
    >
      {created ? (
        <CreatedPanel data={created} onClose={onClose} />
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => { e.preventDefault(); if (valid) mutation.mutate() }}
        >
          <p className="rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 text-[11.5px] leading-relaxed text-text-dim">
            Entra al equipo como entrenador y ve los macrociclos en los que se le
            incluya. Para dar de alta a un atleta, usa{' '}
            <span className="font-semibold text-text">Agregar atleta</span> en la
            sección Atletas: eso crea su ficha y su acceso a la vez.
          </p>

          <Field label="Nombre">
            <input
              className="field"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Nombre y apellido"
            />
          </Field>

          <Field label="Email">
            <input
              className="field"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="entrenador@club.com"
            />
          </Field>

          <Field label="Contraseña temporal (opcional)">
            <input
              className="field"
              type="text"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="Se genera una si lo dejas vacío"
            />
            <p className="mt-1.5 text-[10.5px] text-text-faint">
              Mínimo 8 caracteres. Quien reciba la cuenta debería cambiarla al entrar.
            </p>
          </Field>

          {mutation.isError && (
            <p className="text-[11.5px] text-coral">{(mutation.error as Error).message}</p>
          )}

          <div className="flex justify-end gap-2.5 border-t border-line pt-4">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={!valid || mutation.isPending}>
              <UserPlus size={14} /> {mutation.isPending ? 'Creando…' : 'Crear entrenador'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}

function CreatedPanel({ data, onClose }: { data: MemberCreated; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const password = data.temporary_password ?? ''

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[12.5px] leading-relaxed text-text-dim">
        <span className="font-semibold text-text">{data.member.name}</span> ya puede entrar con{' '}
        <span className="mono text-[12px]">{data.member.email}</span>
        {data.member.swimmer_name && <> y verá la ficha de <span className="font-semibold text-text">{data.member.swimmer_name}</span></>}.
      </p>

      <div>
        <span className="label">Contraseña temporal</span>
        <div className="flex items-center gap-2">
          <code className="mono flex-1 truncate rounded-[10px] border border-line bg-surface-2 px-3 py-2.5 text-[14px]">
            {password}
          </code>
          <button
            type="button"
            className="btn btn-ghost !px-3"
            onClick={() => {
              navigator.clipboard.writeText(password)
                .then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800) })
                .catch(() => undefined)
            }}
            aria-label="Copiar contraseña"
          >
            {copied ? <Check size={14} className="text-mint" /> : <Copy size={14} />}
          </button>
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-amber">
          Cópiala ahora: se guarda cifrada y no hay forma de volver a verla.
        </p>
      </div>

      <div className="flex justify-end border-t border-line pt-4">
        <button className="btn btn-primary" onClick={onClose}>Entendido</button>
      </div>
    </div>
  )
}
