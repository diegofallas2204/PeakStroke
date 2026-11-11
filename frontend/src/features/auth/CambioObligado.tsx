// Cambiar la contraseña temporal antes de entrar (TODO-27).
//
// Una temporal la vio alguien más: el entrenador que dio el alta o quien la
// restableció. Mientras siga puesta, el backend responde 403 a todo salvo a
// este cambio, así que no tiene sentido enseñar la app: solo este formulario y
// la salida.
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { KeyRound, LogOut } from 'lucide-react'
import { api } from '../../lib/api'
import { cerrarSesion } from '../../lib/sesion'
import { CampoDePassword } from './CampoDePassword'
import { ErrorDeFormulario, MarcoDeAcceso } from './MarcoDeAcceso'

const MIN = 8

export function CambioObligado({ nombre }: { nombre: string }) {
  const [temporal, setTemporal] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetida, setRepetida] = useState('')

  // Si sale bien, `api.auth.changePassword` adopta la sesión nueva, que ya no
  // lleva la marca, y la puerta deja pasar: esta pantalla se desmonta sola.
  const cambio = useMutation({
    meta: { errorEnLinea: true },
    mutationFn: () => api.auth.changePassword(temporal, nueva),
  })

  const distintas = repetida.length > 0 && nueva !== repetida
  const igualQueLaTemporal = nueva.length > 0 && nueva === temporal
  const valido = temporal.length > 0 && nueva.length >= MIN && nueva === repetida && !igualQueLaTemporal

  return (
    <MarcoDeAcceso
      titulo={`Hola, ${nombre.split(' ')[0]}`}
      pista="Tu contraseña es temporal y la vio quien te dio de alta. Elige una que solo sepas tú para continuar."
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => { e.preventDefault(); if (valido && !cambio.isPending) cambio.mutate() }}
      >
        <CampoDePassword
          etiqueta="Contraseña temporal" valor={temporal} onCambio={setTemporal}
          autoComplete="current-password" autoFocus
        />
        <CampoDePassword
          etiqueta="Nueva contraseña" valor={nueva} onCambio={setNueva}
          autoComplete="new-password" pista={`Mínimo ${MIN} caracteres.`}
        />
        <CampoDePassword
          etiqueta="Repetir nueva contraseña" valor={repetida} onCambio={setRepetida}
          autoComplete="new-password"
        />

        {distintas && <ErrorDeFormulario texto="Las dos contraseñas no coinciden." />}
        {igualQueLaTemporal && <ErrorDeFormulario texto="La nueva tiene que ser distinta de la temporal." />}
        {cambio.isError && <ErrorDeFormulario texto={(cambio.error as Error).message} />}

        <button type="submit" className="btn btn-primary mt-1 justify-center" disabled={!valido || cambio.isPending}>
          <KeyRound size={15} /> {cambio.isPending ? 'Guardando…' : 'Guardar y entrar'}
        </button>
        <button type="button" className="btn btn-ghost justify-center" onClick={() => void cerrarSesion()}>
          <LogOut size={14} /> Salir
        </button>
      </form>
    </MarcoDeAcceso>
  )
}
