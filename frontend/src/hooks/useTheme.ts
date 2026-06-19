// Tema global de la interfaz: 'navy' (azul marino, por defecto) | 'black' (negro)
// | 'white' (blanco). Store externo mínimo (sin dependencias) sincronizado con
// localStorage y con el atributo data-theme del <html>, que dispara el cambio de
// variables CSS.
import { useSyncExternalStore } from 'react'

export type Theme = 'navy' | 'black' | 'white'

const KEY = 'ps-theme'

function read(): Theme {
  if (typeof localStorage === 'undefined') return 'navy'
  const v = localStorage.getItem(KEY)
  return v === 'black' || v === 'white' ? v : 'navy'
}

function apply(theme: Theme) {
  const root = document.documentElement
  if (theme === 'navy') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', theme)
}

let current: Theme = read()
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setTheme(theme: Theme) {
  current = theme
  localStorage.setItem(KEY, theme)
  apply(theme)
  listeners.forEach((l) => l())
}

/** Aplica el tema persistido lo antes posible (llamar en el arranque). */
export function initTheme() {
  apply(current)
}

export function useTheme(): [Theme, (t: Theme) => void] {
  const theme = useSyncExternalStore(subscribe, () => current, () => current)
  return [theme, setTheme]
}
