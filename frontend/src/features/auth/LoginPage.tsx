// Entrar. Lo único que se ve sin sesión cuando el login está encendido.
//
// No hay «crear cuenta» ni «olvidé mi contraseña» a propósito: hoy la cuenta la
// crea el entrenador y la contraseña la restablece quien opera el servidor. Un
// enlace a algo que no existe sería peor que decir a quién pedírselo.
import { useId, useState } from 'react'
import { LogIn } from 'lucide-react'
import { iniciarSesion } from '../../lib/sesion'
import { CampoDePassword } from './CampoDePassword'
import { ErrorDeFormulario, MarcoDeAcceso } from './MarcoDeAcceso'

export function LoginPage() {
  const idCorreo = useId()
  const [correo, setCorreo] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [entrando, setEntrando] = useState(false)

  const completo = correo.trim().length > 0 && password.length > 0

  const entrar = async () => {
    if (!completo || entrando) return
    setError('')
    setEntrando(true)
    try {
      // Si sale bien, la puerta de sesión desmonta esta pantalla: no hay nada
      // que hacer después.
      await iniciarSesion(correo.trim(), password)
    } catch (e) {
      // `fetch` sin red lanza un TypeError con un texto en inglés que no ayuda.
      setError(e instanceof TypeError
        ? 'No se pudo conectar con el servidor. Comprueba la conexión y vuelve a intentar.'
        : (e as Error).message)
      setEntrando(false)
    }
  }

  return (
    <MarcoDeAcceso titulo="PeakStroke" pista="Entra con el correo con el que te dieron de alta">
      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); void entrar() }}>
        <div>
          <label htmlFor={idCorreo} className="label">Correo</label>
          <input
            id={idCorreo}
            className="field"
            type="email"
            inputMode="email"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            autoFocus
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
          />
        </div>
        <CampoDePassword
          etiqueta="Contraseña"
          valor={password}
          onCambio={setPassword}
          autoComplete="current-password"
        />

        {error && <ErrorDeFormulario texto={error} />}

        <button type="submit" className="btn btn-primary mt-1 justify-center" disabled={!completo || entrando}>
          <LogIn size={15} /> {entrando ? 'Entrando…' : 'Entrar'}
        </button>
        <p className="text-center text-[11px] leading-relaxed text-text-faint">
          ¿No recuerdas tu contraseña? Pídele a tu entrenador que te la restablezca.
        </p>
      </form>
    </MarcoDeAcceso>
  )
}
