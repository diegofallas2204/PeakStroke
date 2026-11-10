// La pila de avisos, abajo a la derecha. Se monta una vez en `App`.
//
// `role="alert"`: un lector de pantalla lo anuncia sin que el foco se mueva, que
// es lo que hace falta cuando el fallo llega después de haber soltado el botón.
import { createPortal } from 'react-dom'
import { CircleAlert, X } from 'lucide-react'
import { cerrarAviso, useAvisos } from '../../lib/avisos'

export function Avisos() {
  const avisos = useAvisos()
  if (!avisos.length) return null
  return createPortal(
    <div className="pointer-events-none fixed inset-x-3 bottom-3 z-[60] flex flex-col items-end gap-2 sm:inset-x-auto sm:right-5 sm:bottom-5">
      {avisos.map((a) => (
        <div
          key={a.id}
          role="alert"
          className="aviso card pointer-events-auto flex w-full max-w-sm items-start gap-2.5 px-3.5 py-3 shadow-2xl"
          style={{ borderColor: 'rgba(251,113,133,.35)' }}
        >
          <CircleAlert size={15} className="mt-0.5 shrink-0 text-coral" />
          <p className="min-w-0 flex-1 text-[12.5px] leading-snug">{a.texto}</p>
          <button
            type="button"
            className="-m-1 shrink-0 rounded-md p-1 text-text-faint hover:text-text"
            onClick={() => cerrarAviso(a.id)}
            aria-label="Cerrar aviso"
          >
            <X size={13} />
          </button>
        </div>
      ))}
    </div>,
    document.body,
  )
}
