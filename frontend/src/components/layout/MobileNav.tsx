// Navegación para pantallas < lg: barra superior compacta + drawer desplegable.
// El drawer reutiliza el mismo contenido del riel de escritorio (NavContent),
// pero siempre expandido, con idénticos colores y acentos por sección.
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { Manta } from '../ui/Manta'
import { activeNavItem } from './navConfig'
import { NavBrand, NavFooter, NavLinks, NavPlanButton } from './NavContent'

export function MobileNav({
  planName, onOpenSwitcher, onOpenSettings,
}: {
  planName?: string
  onOpenSwitcher: () => void
  onOpenSettings: () => void
}) {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)

  // Cerrar al navegar (incluye back/forward del navegador) y con Escape.
  useEffect(() => setOpen(false), [pathname])
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const active = activeNavItem(pathname)
  const ActiveIcon = active.icon

  // Las acciones que abren un modal cierran el drawer: en móvil el modal ocupa
  // la pantalla completa y dejar el panel detrás no aporta contexto.
  const openFromDrawer = (fn: () => void) => () => { setOpen(false); fn() }

  return (
    <>
      {/* ── Barra superior ─────────────────────────────────── */}
      <div className="flex h-14 items-center gap-2.5 border-b border-line bg-[var(--color-sidebar)] px-3 backdrop-blur-xl lg:hidden">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Abrir navegación"
          aria-expanded={open}
          aria-controls="nav-drawer"
          className="nav-item flex size-9 shrink-0 items-center justify-center rounded-[10px] text-text-dim"
          style={{ '--nav-item-color': 'var(--color-accent)' } as React.CSSProperties}
        >
          <Menu size={18} strokeWidth={2.1} />
        </button>

        <span
          className="flex size-8 shrink-0 items-center justify-center rounded-[10px]"
          style={{
            background: 'linear-gradient(135deg,rgba(59,130,246,.18),rgba(34,211,238,.12))',
            border: '1px solid rgba(59,130,246,.25)',
          }}
        >
          <Manta size={22} />
        </span>
        <p className="display hidden text-[14px] font-bold leading-none tracking-tight sm:block">
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

        {/* Sección activa — sustituye al indicador lateral del riel */}
        <span
          className="ml-auto flex min-w-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-semibold"
          style={{ color: active.color, background: `${active.color}16` }}
        >
          <ActiveIcon size={13} strokeWidth={2.2} className="shrink-0" />
          <span className="truncate">{active.label}</span>
        </span>
      </div>

      {/* ── Drawer ─────────────────────────────────────────── */}
      {open &&
        createPortal(
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="nav-scrim absolute inset-0"
              onMouseDown={() => setOpen(false)}
              aria-hidden="true"
            />
            <aside
              id="nav-drawer"
              role="dialog"
              aria-modal="true"
              aria-label="Navegación"
              className="nav-drawer absolute inset-y-0 left-0 flex w-[258px] max-w-[84vw] flex-col overflow-y-auto border-r border-line bg-[var(--color-sidebar)] backdrop-blur-xl"
            >
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Cerrar navegación"
                className="nav-item absolute right-2 top-4 flex size-8 items-center justify-center rounded-[10px] text-text-faint"
                style={{ '--nav-item-color': 'var(--color-text-dim)' } as React.CSSProperties}
              >
                <X size={15} strokeWidth={2.2} />
              </button>

              <NavBrand variant="panel" />
              {planName && (
                <NavPlanButton
                  variant="panel"
                  planName={planName}
                  onClick={openFromDrawer(onOpenSwitcher)}
                />
              )}
              <NavLinks variant="panel" onNavigate={() => setOpen(false)} />
              <NavFooter
                variant="panel"
                onOpenSettings={openFromDrawer(onOpenSettings)}
                onNavigate={() => setOpen(false)}
              />
            </aside>
          </div>,
          document.body,
        )}
    </>
  )
}
