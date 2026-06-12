// Etiqueta de zona de entrenamiento con su color característico.
import { ZONE_META } from '../../lib/constants'

export function ZoneTag({ zone, small = false }: { zone: string; small?: boolean }) {
  const meta = ZONE_META[zone] ?? { label: zone, color: '#8b93b8' }
  return (
    <span
      className={`mono inline-flex items-center rounded-md font-semibold ${
        small ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-[11px]'
      }`}
      style={{ color: meta.color, background: `${meta.color}1a` }}
      title={meta.label}
    >
      {zone}
    </span>
  )
}
