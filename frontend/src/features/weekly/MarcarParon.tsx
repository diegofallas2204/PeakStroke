// Marcar una semana como parón. Sustituye al `prompt()` del navegador, que no
// se podía tematizar, cortaba el texto en el celular y no ofrecía los motivos
// de siempre: aquí son un toque, y el motivo libre sigue siendo opcional.
import { useState } from 'react'
import { PauseCircle } from 'lucide-react'
import type { Week } from '../../lib/types'
import { Field, Modal } from '../../components/ui/primitives'

const MOTIVOS = ['Lesión', 'Enfermedad', 'Vacaciones', 'Exámenes', 'Viaje']

export function MarcarParon({
  week, onCancel, onConfirm,
}: { week: Week | null; onCancel: () => void; onConfirm: (motivo: string | null) => void }) {
  return (
    <Modal open={week != null} onClose={onCancel} title={week ? `Parón · S${week.week_number} (${week.date_label})` : ''}>
      {week && <Cuerpo week={week} onCancel={onCancel} onConfirm={onConfirm} />}
    </Modal>
  )
}

function Cuerpo({ week, onCancel, onConfirm }: { week: Week; onCancel: () => void; onConfirm: (motivo: string | null) => void }) {
  const [motivo, setMotivo] = useState(week.disable_reason ?? '')
  const confirmar = () => onConfirm(motivo.trim() || null)
  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); confirmar() }}>
      <p className="text-[12.5px] text-text-dim">
        La semana no cuenta para el plan: no pide tiempo real y la curva sigue sin ella. Se puede reactivar cuando quieras.
      </p>
      <Field label="Motivo (opcional)">
        <input
          className="field" autoFocus maxLength={200} value={motivo}
          onChange={(e) => setMotivo(e.target.value)} placeholder="Lesión, vacaciones…"
        />
      </Field>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Motivos habituales">
        {MOTIVOS.map((m) => (
          <button
            key={m} type="button" aria-pressed={motivo === m}
            className={`rounded-full border px-3 py-1 text-[11.5px] transition-colors ${
              motivo === m ? 'border-amber text-amber' : 'border-line text-text-dim hover:border-line-strong'
            }`}
            onClick={() => setMotivo(m)}
          >
            {m}
          </button>
        ))}
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancelar</button>
        <button type="submit" className="btn btn-primary"><PauseCircle size={14} /> Marcar parón</button>
      </div>
    </form>
  )
}
