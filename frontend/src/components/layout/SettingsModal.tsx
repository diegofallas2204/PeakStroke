// Ajustes globales: apariencia (tema), modo simplificado y, mientras el login
// esté apagado, el conmutador de identidad de desarrollo.
// Se abre desde el pie del rail de escritorio y del drawer móvil.
import { DevIdentitySwitcher } from '../../features/settings/DevIdentitySwitcher'
import { ThemeSwitcher } from '../../features/settings/ThemeSwitcher'
import { Modal, Toggle } from '../ui/primitives'
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
          <Toggle
            checked={simple}
            onChange={setSimple}
            label="Modo simplificado"
            hint="Solo lo esencial · letras más grandes · sin gráficos"
          />
        </div>
        <DevIdentitySwitcher />
        <p className="text-[9px] text-text-faint">PeakStroke v0.1 · local-first</p>
      </div>
    </Modal>
  )
}
