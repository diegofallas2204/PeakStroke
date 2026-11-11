// El marco de las pantallas de fuera de la app: entrar y cambiar la temporal.
// Una tarjeta centrada con la marca, sin navegación — todavía no hay sesión que
// la justifique.
import type { ReactNode } from 'react'
import { Manta } from '../../components/ui/Manta'

export function MarcoDeAcceso({
  titulo, pista, children,
}: { titulo: string; pista?: ReactNode; children: ReactNode }) {
  return (
    <main className="relative z-10 flex min-h-full w-full items-center justify-center overflow-y-auto px-4 py-10">
      <section className="card w-full max-w-sm p-6 sm:p-7">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <span
            className="flex size-12 items-center justify-center rounded-2xl"
            style={{
              background: 'linear-gradient(135deg,rgba(59,130,246,.18),rgba(34,211,238,.12))',
              border: '1px solid rgba(59,130,246,.25)',
            }}
          >
            <Manta size={34} />
          </span>
          <div>
            <h1 className="display text-[19px] font-bold leading-tight tracking-tight">{titulo}</h1>
            {pista && <p className="mt-1.5 text-[12px] leading-relaxed text-text-dim">{pista}</p>}
          </div>
        </div>
        {children}
      </section>
    </main>
  )
}

/** Un error de formulario. `role="alert"`: se anuncia sin mover el foco. */
export function ErrorDeFormulario({ texto }: { texto: string }) {
  return (
    <p role="alert" className="rounded-lg border border-[rgba(251,113,133,.3)] bg-[rgba(251,113,133,.08)] px-3 py-2 text-[12px] text-coral">
      {texto}
    </p>
  )
}
