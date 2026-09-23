// Conmutador de desarrollo: con qué ojos se está mirando la aplicación.
//
// Solo existe con el login apagado y fuera de producción; `/auth/config` lo dice
// y este componente devuelve null si no. En cuanto se encienda el login real,
// desaparece sin tocar nada.
import { useQuery } from '@tanstack/react-query'
import { Check, ShieldAlert, UserRoundCog } from 'lucide-react'
import { api } from '../../lib/api'
import { limpiarCacheDeIdentidad } from '../../lib/queryClient'
import { Toggle } from '../../components/ui/primitives'
import { setDevIdentity, useDevBypass } from '../../hooks/useDevIdentity'
import { useAuthConfig, useSession } from '../../hooks/useSession'

const ROL = { coach: 'Entrenador', athlete: 'Atleta' } as const

export function DevIdentitySwitcher() {
  const { data: config } = useAuthConfig()
  const { data: yo } = useSession()
  const [bypass, setBypass] = useDevBypass()

  const { data: identidades = [] } = useQuery({
    queryKey: ['dev-identities'],
    queryFn: () => api.auth.devIdentities(),
    staleTime: Infinity,
    retry: false,
    enabled: config?.dev_identities_enabled === true,
  })

  if (!config?.dev_identities_enabled) return null

  return (
    <div>
      <p className="card-title mb-1 flex items-center gap-1.5">
        <UserRoundCog size={13} strokeWidth={2.2} />
        Desarrollo
      </p>
      <p className="mb-3 text-[10.5px] text-text-faint">
        Mira la aplicación con los ojos de cualquier cuenta. Cambiar de identidad
        recarga la página.
      </p>

      <div className="flex flex-col gap-1.5">
        {identidades.map((i) => {
          // Quién eres sale SIEMPRE de `/auth/me`, nunca de lo que este
          // componente cree haber guardado. Discrepar es imposible por
          // construcción: si el backend cayó al usuario por defecto porque el
          // email no existía, la marca aparece donde de verdad estás.
          const activa = yo?.email === i.email
          return (
            <button
              key={i.email}
              type="button"
              onClick={() => !activa && setDevIdentity(i.email, limpiarCacheDeIdentidad)}
              aria-current={activa}
              className={`flex items-center gap-2.5 rounded-xl border px-3 py-2.5 text-left transition-colors ${
                activa
                  ? 'border-accent/40 bg-accent/10'
                  : 'border-line bg-surface-2 hover:border-line-strong'
              }`}
            >
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5">
                  <span className="truncate text-[12.5px] font-semibold">{i.name}</span>
                  {i.is_owner && (
                    <span className="shrink-0 rounded-full bg-surface-3 px-1.5 py-px text-[9px] font-semibold text-text-dim">
                      dueño
                    </span>
                  )}
                </span>
                <span className="mt-px block truncate text-[10.5px] text-text-faint">
                  {ROL[i.role as keyof typeof ROL] ?? i.role}
                  {' · '}
                  {i.swimmer_name ?? 'sin ficha de nadador'}
                </span>
              </span>
              {activa && <Check size={14} strokeWidth={2.4} className="shrink-0 text-accent" />}
            </button>
          )
        })}
      </div>

      <div className="mt-3">
        <Toggle
          checked={bypass}
          onChange={setBypass}
          label="Modo desarrollador"
          hint="Te saltas los guards de rol sin dejar de ver lo que ve esa persona"
          accent="var(--color-warn, #d97706)"
        />
      </div>

      {bypass && (
        <p className="mt-2 flex items-start gap-1.5 text-[10.5px] text-text-faint">
          <ShieldAlert size={12} strokeWidth={2.2} className="mt-px shrink-0" />
          <span>
            Con el modo desarrollador puesto, la aplicación <b>no</b> se comporta
            como lo hará con el login encendido. Apágalo para comprobar de verdad
            lo que ve cada rol.
          </span>
        </p>
      )}
    </div>
  )
}
