// Una consulta que falló, dicha como fallo y con su salida (2026-11-10).
//
// Hasta ahora cada pantalla pintaba un error como si estuviera vacía: con el
// backend caído, Inicio decía «Sin macrociclo activo» y ofrecía crear uno. Es
// mentir sobre el estado, y empuja a hacer algo que no arregla nada. Este es
// el estado de «no se pudo», con el motivo y un Reintentar; cada módulo lo usa
// para lo suyo (`docs/MODULOS.md`, `transversal/sesion`).
import { CloudOff, RefreshCw } from 'lucide-react'
import { EmptyState } from './primitives'

export function ErrorDeCarga({
  error, onReintentar, reintentando = false, que = 'esta pantalla',
}: {
  error: unknown
  onReintentar: () => void
  reintentando?: boolean
  /** Qué no se pudo cargar, para el título: «No se pudo cargar {que}». */
  que?: string
}) {
  // `fetch` sin red lanza un TypeError en inglés que no ayuda a nadie.
  const motivo = error instanceof TypeError
    ? 'No hay conexión con el servidor.'
    : error instanceof Error && error.message
      ? error.message
      : undefined
  return (
    <EmptyState
      icon={<CloudOff size={24} />}
      title={`No se pudo cargar ${que}`}
      hint={motivo}
      action={
        <button className="btn btn-primary" onClick={onReintentar} disabled={reintentando}>
          <RefreshCw size={14} className={reintentando ? 'animate-spin' : ''} /> Reintentar
        </button>
      }
    />
  )
}
