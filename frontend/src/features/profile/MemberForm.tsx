// Alta de una cuenta desde Perfil. No hay registro público: el entrenador crea
// la cuenta y, si quiere, la liga a un nadador ya registrado.
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, UserPlus } from 'lucide-react'
import { api } from '../../lib/api'
import type { MemberCreated, Role } from '../../lib/types'
import { Field, Modal } from '../../components/ui/primitives'

const EMPTY = { swimmerId: '', name: '', email: '', role: 'athlete' as Role, password: '' }

export function MemberForm({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form, setForm] = useState(EMPTY)
  const [created, setCreated] = useState<MemberCreated | null>(null)
  const queryClient = useQueryClient()

  // Solo se ofrecen los nadadores que aún no tienen cuenta: la relación es 1:1.
  const { data: swimmers } = useQuery({
    queryKey: ['swimmers', ''],
    queryFn: () => api.swimmers.list(),
    enabled: open,
  })
  const available = (swimmers ?? []).filter((s) => s.user_id == null)

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
      role: form.role,
      password: form.password ? form.password : null,
      swimmer_id: form.swimmerId ? Number(form.swimmerId) : null,
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

  // Elegir un nadador rellena el nombre: casi siempre coincide.
  const pickSwimmer = (id: string) => {
    const swimmer = available.find((s) => String(s.id) === id)
    setForm((f) => ({ ...f, swimmerId: id, name: swimmer?.name ?? f.name }))
  }

  const valid = form.name.trim().length >= 2 && /.+@.+\..+/.test(form.email) &&
    (!form.password || form.password.length >= 8)

  return (
    <Modal open={open} onClose={onClose} title={created ? 'Cuenta creada' : 'Dar acceso'}>
      {created ? (
        <CreatedPanel data={created} onClose={onClose} />
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => { e.preventDefault(); if (valid) mutation.mutate() }}
        >
          <Field label="Nadador">
            <select
              className="field"
              value={form.swimmerId}
              onChange={(e) => pickSwimmer(e.target.value)}
            >
              <option value="">Sin ligar a una ficha</option>
              {available.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <p className="mt-1.5 text-[10.5px] text-text-faint">
              {available.length
                ? 'Solo aparecen los nadadores que aún no tienen cuenta.'
                : 'Todos los nadadores registrados ya tienen cuenta.'}
            </p>
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Nombre">
              <input
                className="field"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Nombre y apellido"
              />
            </Field>
            <Field label="Rol">
              <select
                className="field"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
              >
                <option value="athlete">Atleta</option>
                <option value="coach">Entrenador</option>
              </select>
            </Field>
          </div>

          <Field label="Email">
            <input
              className="field"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="atleta@club.com"
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
              <UserPlus size={14} /> {mutation.isPending ? 'Creando…' : 'Crear cuenta'}
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
