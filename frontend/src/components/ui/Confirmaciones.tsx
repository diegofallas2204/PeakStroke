// El diálogo de `lib/confirmar.ts`. Se monta una vez, en `App`.
//
// `role="alertdialog"`: un lector de pantalla lo anuncia como una pregunta que
// hay que contestar. El foco va a **Cancelar**: Enter por inercia no borra nada.
import { useEffect, useRef } from 'react'
import { AlertTriangle } from 'lucide-react'
import { responder, useConfirmacionPendiente } from '../../lib/confirmar'
import { Modal } from './primitives'

export function Confirmaciones() {
  const peticion = useConfirmacionPendiente()
  const cancelar = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (peticion) cancelar.current?.focus()
  }, [peticion])

  if (!peticion) return null
  return (
    <Modal open onClose={() => responder(false)} title={peticion.titulo}>
      <div role="alertdialog" aria-label={peticion.titulo} className="flex flex-col gap-5">
        {peticion.texto && (
          <p className="flex items-start gap-2.5 text-[12.5px] leading-relaxed text-text-dim">
            {peticion.peligro && <AlertTriangle size={15} className="mt-0.5 shrink-0 text-coral" />}
            {peticion.texto}
          </p>
        )}
        <div className="flex justify-end gap-2.5">
          <button ref={cancelar} type="button" className="btn btn-ghost" onClick={() => responder(false)}>
            Cancelar
          </button>
          <button
            type="button"
            className={`btn ${peticion.peligro ? 'btn-danger' : 'btn-primary'}`}
            onClick={() => responder(true)}
          >
            {peticion.accion}
          </button>
        </div>
      </div>
    </Modal>
  )
}
