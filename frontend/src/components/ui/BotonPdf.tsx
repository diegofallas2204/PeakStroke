// Botón de descarga a PDF. Vive en `components/ui` porque lo comparten dos
// secciones (simulador y tabla del equipo) y ninguna depende de la otra.
//
// El PDF se arma en el cliente con los datos que ya están en pantalla: no hay
// petición, así que tampoco hay estado de carga que fingir.
import { FileDown } from 'lucide-react'

export function BotonPdf({
  onClick, label = 'PDF', title, disabled = false,
}: {
  onClick: () => void
  /** Texto visible. 'PDF' cuando va pegado a una tabla y el contexto ya se sabe. */
  label?: string
  /** Explicación para el tooltip: qué se lleva exactamente el archivo. */
  title?: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      className="btn btn-ghost !px-3 !py-1.5 text-[11px]"
      onClick={onClick}
      disabled={disabled}
      title={title}
    >
      <FileDown size={13} />
      {label}
    </button>
  )
}
