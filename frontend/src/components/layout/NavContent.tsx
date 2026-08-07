// Cuerpo compartido de la navegación: marca, macrociclo activo, secciones y ajustes.
// Dos presentaciones con el mismo diseño y colores:
//   · 'rail'  → riel de 56px que se despliega al hacer hover (escritorio)
//   · 'panel' → siempre desplegado, dentro del drawer (móvil/tablet)
import { NavLink } from 'react-router-dom'
import { ChevronsUpDown, Settings } from 'lucide-react'
import { Manta } from '../ui/Manta'
import { navItemsFor } from './navConfig'
import { ROLE_META, SECTION_ACCENT } from '../../lib/constants'
import { useRole, useSession } from '../../hooks/useSession'
import { initials } from '../../lib/format'

type Variant = 'rail' | 'panel'

// En el riel los textos aparecen con el hover del <aside>; en el panel están fijos.
const revealed = (variant: Variant, delay: string) =>
  variant === 'panel'
    ? ''
    : `opacity-0 transition-opacity ${delay} duration-200 group-hover/aside:opacity-100`

// El padding horizontal también se expande con el hover en el riel.
const padded = (variant: Variant) =>
  variant === 'panel' ? 'px-3' : 'px-1.5 group-hover/aside:px-3'

export function NavBrand({ variant }: { variant: Variant }) {
  return (
    <div className="flex shrink-0 items-center gap-2.5 overflow-hidden px-[13px] pb-4 pt-6">
      <span
        className="flex size-9 shrink-0 items-center justify-center rounded-xl"
        style={{
          background: 'linear-gradient(135deg,rgba(59,130,246,.18),rgba(34,211,238,.12))',
          border: '1px solid rgba(59,130,246,.25)',
        }}
      >
        <Manta size={26} />
      </span>
      <div className={`overflow-hidden whitespace-nowrap ${revealed(variant, 'delay-100')}`}>
        <p className="display text-[15.5px] font-bold leading-none tracking-tight">
          Peak
          <span
            style={{
              background: 'linear-gradient(135deg,#3b82f6,#22d3ee)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            Stroke
          </span>
        </p>
        <p className="mt-1 text-[9px] uppercase tracking-[0.22em] text-text-faint">
          Performance Planner
        </p>
      </div>
    </div>
  )
}

export function NavPlanButton({
  variant, planName, onClick,
}: { variant: Variant; planName: string; onClick: () => void }) {
  const panel = variant === 'panel'
  return (
    <div className="mx-2 mb-1 shrink-0">
      <button
        type="button"
        onClick={onClick}
        aria-label="Cambiar macrociclo de trabajo"
        className={[
          'flex w-full items-center gap-2.5 rounded-[10px] py-[9px]',
          padded(variant),
          panel
            ? 'border border-[rgba(59,130,246,.15)] bg-[rgba(59,130,246,.07)]'
            : 'border border-transparent bg-transparent group-hover/aside:border-[rgba(59,130,246,.15)] group-hover/aside:bg-[rgba(59,130,246,.07)]',
          'transition-[background-color,border-color,padding] duration-300 ease-in-out',
        ].join(' ')}
      >
        {/* Dot — siempre visible; caja azul solo cuando está expandido */}
        <span
          className={`flex size-[28px] shrink-0 items-center justify-center rounded-lg transition-[background-color] duration-300 ${
            panel ? 'bg-[rgba(59,130,246,.15)]' : 'bg-transparent group-hover/aside:bg-[rgba(59,130,246,.15)]'
          }`}
        >
          <span className="pulse-dot size-[7px] rounded-full bg-mint" />
        </span>

        <div className={`min-w-0 flex-1 overflow-hidden ${revealed(variant, 'delay-100')}`}>
          <p className="text-[8.5px] font-bold uppercase tracking-[0.14em] leading-none text-text-faint">
            Macrociclo activo
          </p>
          <p className="mt-[3px] truncate text-left text-[12px] font-semibold leading-none">
            {planName}
          </p>
        </div>
        <ChevronsUpDown size={11} className={`shrink-0 text-text-faint ${revealed(variant, 'delay-100')}`} />
      </button>
    </div>
  )
}

export function NavLinks({
  variant, onNavigate,
}: { variant: Variant; onNavigate?: () => void }) {
  // Mientras la sesión carga, `navItemsFor` devuelve lista vacía y el rail sale
  // sin secciones en vez de con las del rol equivocado. Es el mismo trato que
  // esta pantalla ya le da al avatar: preferir un hueco un instante a enseñar
  // algo que habrá que quitar.
  const items = navItemsFor(useRole())
  return (
    <nav className="flex-1 py-1">
      {items.map(({ to, label, icon: Icon, color }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          onClick={onNavigate}
          style={({ isActive }) =>
            ({
              '--nav-item-color': color,
              ...(isActive ? { background: `${color}16`, color } : {}),
            } as React.CSSProperties)
          }
          className={({ isActive }) =>
            `nav-item relative mx-2 flex items-center gap-2.5 rounded-[10px] py-[9px] text-[12.5px] font-medium transition-[background-color,color,padding] duration-300 ease-in-out ${padded(variant)} ${
              isActive ? 'nav-item--active' : 'text-text-dim'
            }`
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <span
                  className="nav-indicator absolute -left-2 top-[calc(50%-10px)] h-5 w-[3px] rounded-r-full"
                  style={{ background: color, boxShadow: `0 0 10px 2px ${color}55` }}
                />
              )}
              <span
                className="flex size-[28px] shrink-0 items-center justify-center rounded-lg transition-colors duration-200"
                style={isActive ? { background: `${color}20` } : {}}
              >
                <Icon size={14.5} strokeWidth={2.1} />
              </span>
              <span
                className={`overflow-hidden whitespace-nowrap leading-none ${revealed(variant, 'delay-[80ms]')}`}
              >
                {label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

// Pie del rail: identidad (Perfil) y preferencias (Ajustes). Van juntos porque
// son las dos secciones "de sistema", ajenas al dominio de las 8 de arriba —
// pero separadas entre sí: Perfil es quién soy, Ajustes es cómo se ve la app.
export function NavFooter({
  variant, onOpenSettings, onNavigate,
}: { variant: Variant; onOpenSettings: () => void; onNavigate?: () => void }) {
  const { data: session } = useSession()
  const color = SECTION_ACCENT['/perfil']
  const role = session ? ROLE_META[session.role] : undefined

  return (
    <div className="shrink-0 border-t border-line px-2 py-2">
      <NavLink
        to="/perfil"
        onClick={onNavigate}
        style={({ isActive }) =>
          ({
            '--nav-item-color': color,
            ...(isActive ? { background: `${color}16`, color } : {}),
          } as React.CSSProperties)
        }
        className={({ isActive }) =>
          `nav-item relative flex items-center gap-2.5 rounded-[10px] py-[9px] transition-[background-color,color,padding] duration-300 ease-in-out ${padded(variant)} ${
            isActive ? 'nav-item--active' : 'text-text-dim'
          }`
        }
      >
        {({ isActive }) => (
          <>
            {isActive && (
              <span
                className="nav-indicator absolute -left-2 top-[calc(50%-10px)] h-5 w-[3px] rounded-r-full"
                style={{ background: color, boxShadow: `0 0 10px 2px ${color}55` }}
              />
            )}
            {/* Avatar en vez de icono: en el riel colapsado las iniciales
                identifican la cuenta de un vistazo, sin desplegar. */}
            <span
              className="display flex size-[28px] shrink-0 items-center justify-center rounded-lg text-[10.5px] font-bold"
              style={{
                color,
                background: `${color}1c`,
                border: `1px solid ${color}33`,
              }}
            >
              {session ? initials(session.name) : '··'}
            </span>
            <div className={`min-w-0 flex-1 overflow-hidden ${revealed(variant, 'delay-[80ms]')}`}>
              <p className="truncate text-left text-[12.5px] font-semibold leading-none">
                {session?.name ?? 'Perfil'}
              </p>
              <p className="mt-[3px] truncate text-left text-[9px] font-bold uppercase tracking-[0.14em] leading-none text-text-faint">
                {role?.label ?? 'Cuenta'}
              </p>
            </div>
          </>
        )}
      </NavLink>

      <button
        type="button"
        onClick={onOpenSettings}
        className={`nav-item mt-0.5 flex w-full items-center gap-2.5 rounded-[10px] py-[9px] text-[12.5px] font-medium text-text-dim transition-[background-color,color,padding] duration-300 ease-in-out ${padded(variant)}`}
        style={{ '--nav-item-color': 'var(--color-text-dim)' } as React.CSSProperties}
      >
        <span className="flex size-[28px] shrink-0 items-center justify-center rounded-lg">
          <Settings size={14.5} strokeWidth={2.1} />
        </span>
        <span className={`overflow-hidden whitespace-nowrap leading-none ${revealed(variant, 'delay-[80ms]')}`}>
          Ajustes
        </span>
      </button>
    </div>
  )
}
