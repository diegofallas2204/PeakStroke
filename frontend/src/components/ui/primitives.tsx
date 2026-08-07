// Primitivas de UI compartidas: Card, Badge, botones, campos, modal, vacíos.
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { STATUS_META } from '../../lib/constants'

export function Card({
  title, action, children, className = '', animate = true, flush = false,
}: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  animate?: boolean
  // flush: el cuerpo va a ras de los bordes (tablas full-bleed), pero el
  // encabezado conserva su padding para que el título no toque el borde.
  flush?: boolean
}) {
  return (
    <section
      className={`card ${flush ? '' : 'p-5'} ${className}`}
      {...(animate ? { 'data-animate': '' } : {})}
    >
      {(title || action) && (
        <header
          className={`flex items-center justify-between gap-3 ${flush ? 'px-5 pb-4 pt-5' : 'mb-4'}`}
        >
          {title && <h3 className="card-title">{title}</h3>}
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

export function StatusBadge({ status }: { status: string | null }) {
  const meta = STATUS_META[status ?? 'pending'] ?? STATUS_META.pending
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold"
      style={{ color: meta.color, background: meta.bg }}
    >
      <span className="size-1.5 rounded-full" style={{ background: meta.color }} />
      {meta.label}
    </span>
  )
}

export function Chip({
  children, color = '#3b82f6',
}: { children: ReactNode; color?: string }) {
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider"
      style={{ color, background: `${color}1f` }}
    >
      {children}
    </span>
  )
}

/** Selector de una opción entre pocas. Para filtros y vistas alternativas. */
export function Segmented<T extends string>({
  value, options, onChange, accent = 'var(--color-accent)', label,
}: {
  value: T
  options: { value: T; label: ReactNode }[]
  onChange: (value: T) => void
  accent?: string
  label?: string
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex shrink-0 items-center gap-0.5 rounded-[10px] border border-line bg-surface-2 p-0.5"
    >
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={`rounded-lg px-2.5 py-1 text-[11.5px] font-semibold transition-colors duration-200 ${
              active ? '' : 'text-text-dim hover:text-text'
            }`}
            style={active ? { color: accent, background: `${accent}1f` } : undefined}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

export function Field({
  label, children, className = '',
}: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <span className="label">{label}</span>
      {children}
    </div>
  )
}

export function Modal({
  open, onClose, title, children, wide = false,
}: {
  open: boolean
  onClose: () => void
  title: ReactNode
  children: ReactNode
  wide?: boolean
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  // Portal a <body>: evita que un ancestro con backdrop-filter (p. ej. el sidebar)
  // capture el position:fixed y comprima el modal a su ancho.
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: 'rgba(4,5,10,.72)', backdropFilter: 'blur(6px)' }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className={`card max-h-[88vh] w-full overflow-y-auto p-6 shadow-2xl ${wide ? 'max-w-4xl' : 'max-w-xl'}`}
        style={{ animation: 'modal-in .28s cubic-bezier(.2,.9,.3,1.2) both' }}
      >
        <style>{`@keyframes modal-in { from { opacity: 0; transform: translateY(16px) scale(.97); } to { opacity: 1; transform: none; } }`}</style>
        <header className="mb-5 flex items-center justify-between">
          <h2 className="display text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="btn btn-ghost !p-2" aria-label="Cerrar">
            <X size={15} />
          </button>
        </header>
        {children}
      </div>
    </div>,
    document.body,
  )
}

export function EmptyState({
  icon, title, hint, action,
}: { icon: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-14 text-center" data-animate>
      <div
        className="flex size-14 items-center justify-center rounded-2xl text-accent-soft"
        style={{ background: 'rgba(59,130,246,.1)', border: '1px solid rgba(59,130,246,.2)' }}
      >
        {icon}
      </div>
      <p className="display text-base font-semibold">{title}</p>
      {hint && <p className="max-w-sm text-xs text-text-dim">{hint}</p>}
      {action}
    </div>
  )
}

/**
 * Interruptor de dos estados con su etiqueta y su explicación.
 *
 * `role="switch"` + `aria-checked` en vez de un checkbox estilado: un lector de
 * pantalla anuncia "activado/desactivado" en vez de "casilla marcada", que es lo
 * que esto es de verdad.
 */
export function Toggle({
  checked, onChange, label, hint, accent = 'var(--color-accent)',
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  hint?: string
  accent?: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between rounded-xl border border-line bg-surface-2 px-4 py-3 text-left transition-colors hover:border-line-strong"
    >
      <div className="min-w-0">
        <p className="text-[13px] font-semibold">{label}</p>
        {hint && <p className="mt-0.5 text-[10.5px] text-text-faint">{hint}</p>}
      </div>
      <span
        className="relative ml-4 flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-200"
        style={{ background: checked ? accent : 'var(--color-surface-3)' }}
      >
        <span
          className="absolute h-4 w-4 rounded-full bg-white shadow transition-transform duration-200"
          style={{ transform: checked ? 'translateX(22px)' : 'translateX(4px)' }}
        />
      </span>
    </button>
  )
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div
        className="size-8 animate-spin rounded-full border-2 border-line"
        style={{ borderTopColor: '#3b82f6' }}
      />
    </div>
  )
}
