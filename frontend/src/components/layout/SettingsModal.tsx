// Ajustes globales: apariencia (tema) y modo simplificado.
// Se abre desde el pie del rail de escritorio y del drawer móvil.
import { ThemeSwitcher } from '../../features/settings/ThemeSwitcher'
import { Modal } from '../ui/primitives'
import { useSimpleMode } from '../../hooks/useSimpleMode'

export function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [simple, setSimple] = useSimpleMode()
  return (
    <Modal open={open} onClose={onClose} title="Ajustes">
      <div className="flex flex-col gap-5 py-1">
        <div>
          <p className="card-title mb-3">Apariencia</p>
          <ThemeSwitcher />
        </div>
        <div>
          <p className="card-title mb-3">Vista</p>
          <button
            type="button"
            role="switch"
            aria-checked={simple}
            onClick={() => setSimple(!simple)}
            className="flex w-full items-center justify-between rounded-xl border border-line bg-surface-2 px-4 py-3 transition-colors hover:border-line-strong"
          >
            <div className="text-left">
              <p className="text-[13px] font-semibold">Modo simplificado</p>
              <p className="mt-0.5 text-[10.5px] text-text-faint">Solo lo esencial · letras más grandes · sin gráficos</p>
            </div>
            <span
              className="relative ml-4 flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-200"
              style={{ background: simple ? 'var(--color-accent)' : 'var(--color-surface-3)' }}
            >
              <span
                className="absolute h-4 w-4 rounded-full bg-white shadow transition-transform duration-200"
                style={{ transform: simple ? 'translateX(22px)' : 'translateX(4px)' }}
              />
            </span>
          </button>
        </div>
        <p className="text-[9px] text-text-faint">PeakStroke v0.1 · local-first</p>
      </div>
    </Modal>
  )
}
