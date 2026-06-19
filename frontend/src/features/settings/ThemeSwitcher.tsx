// Selector de tema compacto para el sidebar (Ajustes).
// Tres temas de interfaz; el contenedor queda listo para sumar más ajustes.
import { useTheme, type Theme } from '../../hooks/useTheme'

const THEMES: { value: Theme; label: string; swatch: string; ring: string }[] = [
  { value: 'navy', label: 'Azul marino', swatch: 'linear-gradient(135deg,#0b1322,#18253f)', ring: '#3b82f6' },
  { value: 'black', label: 'Negro', swatch: 'linear-gradient(135deg,#000000,#1e1e1e)', ring: '#3b82f6' },
  { value: 'white', label: 'Blanco', swatch: 'linear-gradient(135deg,#ffffff,#e2e8f0)', ring: '#3b82f6' },
]

export function ThemeSwitcher() {
  const [theme, setTheme] = useTheme()

  return (
    <div>
      <p className="mb-2 text-[9px] font-bold uppercase tracking-[0.15em] text-text-faint">
        Tema
      </p>
      <div className="flex gap-2">
        {THEMES.map((t) => {
          const active = theme === t.value
          return (
            <button
              key={t.value}
              onClick={() => setTheme(t.value)}
              title={t.label}
              aria-label={`Tema ${t.label}`}
              aria-pressed={active}
              className="size-8 rounded-lg border transition-all duration-200"
              style={{
                background: t.swatch,
                borderColor: active ? t.ring : 'var(--color-line-strong)',
                boxShadow: active ? `0 0 0 2px ${t.ring}55` : 'none',
              }}
            />
          )
        })}
      </div>
    </div>
  )
}
