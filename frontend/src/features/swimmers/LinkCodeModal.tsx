// Emitir, enseñar y revocar el código que liga una ficha con una cuenta.
//
// El código se puede volver a leer aquí tantas veces como haga falta —a
// diferencia de la contraseña temporal, que solo se ve una vez—. Es a propósito:
// lo normal es dictarlo, perderlo y tener que repetirlo, y obligar a reemitir
// por eso dejaría códigos vivos sueltos. Lo que sí ocurre al reemitir es que el
// anterior muere; eso lo garantiza el backend.
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, KeyRound, RefreshCw, Trash2 } from 'lucide-react'
import { api } from '../../lib/api'
import type { LinkCode, Swimmer } from '../../lib/types'
import { Modal } from '../../components/ui/primitives'

/** «caduca en 2 d 5 h». Por debajo de una hora, en minutos: ahí sí urge. */
function caducaEn(iso: string): string {
  const minutos = Math.round((new Date(iso).getTime() - Date.now()) / 60000)
  if (minutos <= 0) return 'caducado'
  if (minutos < 60) return `caduca en ${minutos} min`
  const horas = Math.floor(minutos / 60)
  if (horas < 24) return `caduca en ${horas} h`
  return `caduca en ${Math.floor(horas / 24)} d ${horas % 24} h`
}

export function LinkCodeModal({
  swimmer, code, onClose,
}: { swimmer: Swimmer | null; code: LinkCode | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [copied, setCopied] = useState(false)

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ['link-codes'] })
    queryClient.invalidateQueries({ queryKey: ['swimmers'] })
  }
  const emitir = useMutation({
    mutationFn: () => api.linkCodes.issue(swimmer!.id),
    onSuccess: refrescar,
  })
  const revocar = useMutation({
    mutationFn: () => api.linkCodes.revoke(code!.id),
    onSuccess: () => { refrescar(); onClose() },
  })

  const error = (emitir.error ?? revocar.error) as Error | undefined

  return (
    <Modal open={swimmer != null} onClose={onClose} title={`Dar acceso · ${swimmer?.name ?? ''}`}>
      <div className="flex flex-col gap-4">
        <p className="text-[12.5px] leading-relaxed text-text-dim">
          Entrégale este código a <span className="font-semibold text-text">{swimmer?.name}</span>.
          Al canjearlo desde su perfil, su cuenta queda ligada a esta ficha y entra
          al equipo. Hasta entonces no hay ninguna relación entre las dos.
        </p>

        {code ? (
          <div>
            <span className="label">Código de vinculación</span>
            <div className="flex items-center gap-2">
              <code className="display flex-1 truncate rounded-[10px] border border-line bg-surface-2 px-3 py-3 text-center text-[22px] font-bold tracking-[0.18em]">
                {code.code}
              </code>
              <button
                type="button"
                className="btn btn-ghost !px-3"
                onClick={() => {
                  navigator.clipboard.writeText(code.code)
                    .then(() => { setCopied(true); setTimeout(() => setCopied(false), 1800) })
                    .catch(() => undefined)
                }}
                aria-label="Copiar código"
              >
                {copied ? <Check size={14} className="text-mint" /> : <Copy size={14} />}
              </button>
            </div>
            <p className="mt-2 text-[11px] text-amber">
              Un solo uso · {caducaEn(code.expires_at)}
            </p>
          </div>
        ) : (
          <p className="rounded-xl border border-line bg-surface-2 px-3.5 py-3 text-[12px] text-text-faint">
            Esta ficha no tiene ningún código vivo.
          </p>
        )}

        {error && <p className="text-[11.5px] text-coral">{error.message}</p>}

        <div className="flex justify-between gap-2.5 border-t border-line pt-4">
          {code ? (
            <button
              className="btn btn-danger"
              disabled={revocar.isPending}
              onClick={() => {
                if (confirm('¿Revocar este código? Dejará de servir de inmediato.'))
                  revocar.mutate()
              }}
            >
              <Trash2 size={13.5} /> Revocar
            </button>
          ) : <span />}
          <button
            className="btn btn-primary"
            disabled={emitir.isPending}
            onClick={() => emitir.mutate()}
          >
            {code ? <RefreshCw size={13.5} /> : <KeyRound size={13.5} />}
            {code ? 'Generar otro' : 'Generar código'}
          </button>
        </div>

        {code && (
          <p className="text-[10.5px] leading-relaxed text-text-faint">
            Generar otro invalida el actual: no pueden convivir dos códigos vivos
            para la misma ficha.
          </p>
        )}
      </div>
    </Modal>
  )
}
