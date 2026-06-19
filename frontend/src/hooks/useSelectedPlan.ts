// Macrociclo "de trabajo" que se está visualizando en el sistema.
// Es una selección puramente de cliente (no altera el estado del servidor):
// persiste en localStorage y permite cambiar entre macrociclos para inspeccionar
// cualquiera —activo, completado, inactivo o suspendido— sin perder el contexto.
import { useSyncExternalStore } from 'react'

const KEY = 'ps-selected-plan'

function read(): number | null {
  if (typeof localStorage === 'undefined') return null
  const raw = localStorage.getItem(KEY)
  const id = raw ? Number(raw) : NaN
  return Number.isFinite(id) ? id : null
}

let current: number | null = read()
const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setSelectedPlan(id: number | null) {
  current = id
  if (id == null) localStorage.removeItem(KEY)
  else localStorage.setItem(KEY, String(id))
  listeners.forEach((l) => l())
}

export function useSelectedPlanId(): number | null {
  return useSyncExternalStore(subscribe, () => current, () => current)
}
