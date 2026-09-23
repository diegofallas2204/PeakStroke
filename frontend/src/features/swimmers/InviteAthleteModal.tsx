// Agregar un atleta al equipo por el correo con el que se registra al sistema.
//
// **Un gesto donde antes había tres.** Dar de alta a una persona pedía crear la
// cuenta en Perfil, crear la ficha en Atletas y después emitir el código para
// unirlas — tres formularios, en dos secciones, para la misma persona. Ficha y
// cuenta siempre fueron la misma persona vista desde dos sitios; esto lo dice en
// la interfaz.
//
// Lo que NO hace: meter a nadie en el equipo. La cuenta nace en el pool del
// sistema, sin club, y entra cuando canjea el código desde su perfil. Por eso
// esto se llama invitar y no añadir.
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, UserPlus } from 'lucide-react'
import { api } from '../../lib/api'
import type { InviteResult } from '../../lib/types'
import { SPECIALTIES, STROKES } from '../../lib/constants'
import { Field, Modal } from '../../components/ui/primitives'

const EMPTY = {
  email: '', name: '', birth_date: '', gender: '',
  specialty: 'medio_fondo', main_stroke: 'libre',
}

export function InviteAthleteModal({
  open, onClose,
}: { open: boolean; onClose: () => void }) {
  const [form, setForm] = useState(EMPTY)
  const [result, setResult] = useState<InviteResult | null>(null)
  const queryClient = useQueryClient()

  // Al abrir se limpia. Ajuste de estado durante el render (patrón oficial de
  // React) en vez de efecto, igual que SwimmerForm y MemberForm.
  const [prevOpen, setPrevOpen] = useState(open)
  if (prevOpen !== open) {
    setPrevOpen(open)
    if (open) { setForm(EMPTY); setResult(null) }
  }

  const invitar = useMutation({
    mutationFn: () => api.linkCodes.invite({
      email: form.email.trim(),
      name: form.name.trim(),
      birth_date: form.birth_date || null,
      gender: form.gender || null,
      specialty: form.specialty,
      main_stroke: form.main_stroke,
    }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['swimmers'] })
      queryClient.invalidateQueries({ queryKey: ['link-codes'] })
      // El código —y la contraseña, si la hubo— hay que enseñarlos antes de
      // cerrar: la contraseña no se puede volver a consultar nunca.
      setResult(data)
    },
  })

  const valido = form.name.trim().length >= 2 && /.+@.+\..+/.test(form.email)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={result ? 'Atleta agregado' : 'Agregar atleta al equipo'}
    >
      {result ? (
        <Credenciales result={result} nombre={form.name.trim()} onClose={onClose} />
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => { e.preventDefault(); if (valido) invitar.mutate() }}
        >
          <p className="rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 text-[11.5px] leading-relaxed text-text-dim">
            Usa el correo con el que el atleta se registra al sistema. Se creará
            su ficha y un código de un solo uso que caduca a los 3 días; entra al
            equipo cuando lo canjee desde su perfil.
          </p>

          <Field label="Correo">
            <input
              className="field"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="atleta@club.com"
            />
          </Field>

          <Field label="Nombre">
            <input
              className="field"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Nombre y apellido"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Fecha de nacimiento">
              <input
                className="field"
                type="date"
                value={form.birth_date}
                onChange={(e) => setForm({ ...form, birth_date: e.target.value })}
              />
            </Field>
            <Field label="Género">
              <select
                className="field"
                value={form.gender}
                onChange={(e) => setForm({ ...form, gender: e.target.value })}
              >
                <option value="">Sin especificar</option>
                <option value="F">Femenino</option>
                <option value="M">Masculino</option>
              </select>
            </Field>
            <Field label="Especialidad">
              <select
                className="field"
                value={form.specialty}
                onChange={(e) => setForm({ ...form, specialty: e.target.value })}
              >
                {SPECIALTIES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Estilo principal">
              <select
                className="field"
                value={form.main_stroke}
                onChange={(e) => setForm({ ...form, main_stroke: e.target.value })}
              >
                {STROKES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </Field>
          </div>

          {invitar.isError && (
            <p className="text-[11.5px] text-coral">{(invitar.error as Error).message}</p>
          )}

          <div className="flex justify-end gap-2.5 border-t border-line pt-4">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={!valido || invitar.isPending}>
              <UserPlus size={14} /> {invitar.isPending ? 'Agregando…' : 'Agregar atleta'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  )
}

function Credenciales({
  result, nombre, onClose,
}: { result: InviteResult; nombre: string; onClose: () => void }) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[12.5px] leading-relaxed text-text-dim">
        <span className="font-semibold text-text">{nombre}</span> ya está en tu
        lista de atletas.{' '}
        {result.account_created
          ? 'Se le creó una cuenta: entrégale las dos cosas de abajo.'
          : 'Ya tenía cuenta en el sistema, así que entra con su contraseña de siempre.'}
      </p>

      <Copiable
        etiqueta="Código de vinculación"
        valor={result.link_code.code}
        nota="Un solo uso · caduca a los 3 días. Se puede volver a consultar desde la ficha del atleta."
        grande
      />

      {result.temporary_password && (
        <Copiable
          etiqueta="Contraseña temporal"
          valor={result.temporary_password}
          nota="Cópiala ahora: se guarda cifrada y no hay forma de volver a verla."
          alerta
        />
      )}

      <div className="flex justify-end border-t border-line pt-4">
        <button className="btn btn-primary" onClick={onClose}>Entendido</button>
      </div>
    </div>
  )
}

function Copiable({
  etiqueta, valor, nota, grande = false, alerta = false,
}: {
  etiqueta: string; valor: string; nota: string; grande?: boolean; alerta?: boolean
}) {
  const [copiado, setCopiado] = useState(false)
  return (
    <div>
      <span className="label">{etiqueta}</span>
      <div className="flex items-center gap-2">
        <code
          className={`flex-1 truncate rounded-[10px] border border-line bg-surface-2 px-3 ${
            grande
              ? 'display py-3 text-center text-[22px] font-bold tracking-[0.18em]'
              : 'mono py-2.5 text-[14px]'
          }`}
        >
          {valor}
        </code>
        <button
          type="button"
          className="btn btn-ghost !px-3"
          onClick={() => {
            navigator.clipboard.writeText(valor)
              .then(() => { setCopiado(true); setTimeout(() => setCopiado(false), 1800) })
              .catch(() => undefined)
          }}
          aria-label={`Copiar ${etiqueta.toLowerCase()}`}
        >
          {copiado ? <Check size={14} className="text-mint" /> : <Copy size={14} />}
        </button>
      </div>
      <p className={`mt-2 text-[11px] leading-relaxed ${alerta ? 'text-amber' : 'text-text-faint'}`}>
        {nota}
      </p>
    </div>
  )
}
