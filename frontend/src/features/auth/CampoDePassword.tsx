// Un campo de contraseña con su ojo para verla.
//
// Poder ver lo que se teclea evita el error más común de un login —una letra
// mal— sin tener que borrar y empezar. El ojo es un botón de verdad, con nombre
// y estado (`aria-pressed`), y no roba el foco del campo al pulsarlo con el ratón.
import { useId, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'

export function CampoDePassword({
  etiqueta, valor, onCambio, autoComplete, autoFocus = false, pista,
}: {
  etiqueta: string
  valor: string
  onCambio: (valor: string) => void
  autoComplete: 'current-password' | 'new-password'
  autoFocus?: boolean
  pista?: string
}) {
  const id = useId()
  const [visible, setVisible] = useState(false)
  return (
    <div>
      <label htmlFor={id} className="label">{etiqueta}</label>
      <div className="relative">
        <input
          id={id}
          className="field !pr-10"
          type={visible ? 'text' : 'password'}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          value={valor}
          onChange={(e) => onCambio(e.target.value)}
        />
        <button
          type="button"
          className="absolute right-1 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-text-faint hover:text-text"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => setVisible(!visible)}
          aria-label="Ver la contraseña"
          aria-pressed={visible}
          title={visible ? 'Ocultar' : 'Ver'}
        >
          {visible ? <EyeOff size={15} /> : <Eye size={15} />}
        </button>
      </div>
      {pista && <p className="mt-1.5 text-[10.5px] text-text-faint">{pista}</p>}
    </div>
  )
}
