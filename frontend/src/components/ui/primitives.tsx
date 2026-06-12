// Primitivas de UI compartidas: Card, Badge, botones, campos, modal, vacíos.
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { X } from 'lucide-react'
import { STATUS_META } from '../../lib/constants'

export function Card({
  title, action, children, className = '', animate = true,
}: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  animate?: boolean
}) {
  return (
    <section className={`card p-5 ${className}`} {...(animate ? { 'data-animate': '' } : {})}>
      {(title || action) && (
        <header className="mb-4 flex items-center justify-between gap-3">
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
  children, color = '#8b5cf6',
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
  return (
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
    </div>
  )
}

export function EmptyState({
  icon, title, hint, action,
}: { icon: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-14 text-center" data-animate>
      <div
        className="flex size-14 items-center justify-center rounded-2xl text-violet-soft"
        style={{ background: 'rgba(139,92,246,.1)', border: '1px solid rgba(139,92,246,.2)' }}
      >
        {icon}
      </div>
      <p className="display text-base font-semibold">{title}</p>
      {hint && <p className="max-w-sm text-xs text-text-dim">{hint}</p>}
      {action}
    </div>
  )
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div
        className="size-8 animate-spin rounded-full border-2 border-line"
        style={{ borderTopColor: '#8b5cf6' }}
      />
    </div>
  )
}
