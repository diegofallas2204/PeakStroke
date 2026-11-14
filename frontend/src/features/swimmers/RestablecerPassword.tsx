// Restablecer la contraseña de un atleta desde su página (2026-11-13).
//
// El «olvidé mi contraseña» de la app: el entrenador le pone una temporal, la
// ve UNA vez y se la entrega. Al entrar, el atleta tiene que cambiarla (la
// cuenta queda marcada) y todas sus sesiones abiertas se cortan. Solo sobre
// atletas: la regla la impone el backend (`POST /auth/members/{id}/reset-password`).
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Check, Copy, RotateCcwKey } from 'lucide-react'
import { api } from '../../lib/api'
import { confirmar } from '../../lib/confirmar'
import { IconButton, Modal } from '../../components/ui/primitives'

export function RestablecerPassword({ userId, nombre }: { userId: number; nombre: string }) {
  const [temporal, setTemporal] = useState<string | null>(null)
  const [copiada, setCopiada] = useState(false)

  const restablecer = useMutation({
    mutationFn: () => api.auth.resetPassword(userId),
    onSuccess: (r) => { setCopiada(false); setTemporal(r.temporary_password) },
  })

  const pedir = async () => {
    if (await confirmar({
      titulo: `¿Restablecer la contraseña de ${nombre}?`,
      texto: 'La de ahora deja de servir y se cierran todas sus sesiones. Verás una temporal una sola vez; al entrar tendrá que cambiarla.',
      accion: 'Restablecer', peligro: true,
    })) restablecer.mutate()
  }

  const copiar = async () => {
    if (!temporal) return
    try {
      await navigator.clipboard.writeText(temporal)
      setCopiada(true)
    } catch { /* sin permiso de portapapeles: se copia a mano */ }
  }

  return (
    <>
      <IconButton label={`Restablecer la contraseña de ${nombre}`} onClick={pedir} disabled={restablecer.isPending}>
        <RotateCcwKey size={14} />
      </IconButton>
      <Modal open={temporal != null} onClose={() => setTemporal(null)} title={`Contraseña temporal · ${nombre}`}>
        <div className="flex flex-col gap-4">
          <p className="text-[12.5px] leading-relaxed text-text-dim">
            Entrégasela en persona. <span className="font-semibold text-text">No se vuelve a mostrar</span>, y
            al entrar tendrá que elegir una propia.
          </p>
          <div className="flex items-center gap-2">
            <code className="mono flex-1 select-all rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 text-[15px] font-semibold tracking-wide">
              {temporal}
            </code>
            <IconButton label={copiada ? 'Copiada' : 'Copiar'} onClick={copiar}>
              {copiada ? <Check size={15} className="text-mint" /> : <Copy size={15} />}
            </IconButton>
          </div>
          <div className="flex justify-end border-t border-line pt-4">
            <button className="btn btn-primary" onClick={() => setTemporal(null)}>Listo</button>
          </div>
        </div>
      </Modal>
    </>
  )
}
