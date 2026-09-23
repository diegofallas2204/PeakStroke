import { useSyncExternalStore } from 'react'

const KEY = 'ps-simple-mode'

function read(): boolean {
  if (typeof localStorage === 'undefined') return false
  return localStorage.getItem(KEY) === 'true'
}

function apply(simple: boolean) {
  if (simple) document.documentElement.setAttribute('data-simple', '')
  else document.documentElement.removeAttribute('data-simple')
}

let current: boolean = read()
apply(current)

const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setSimpleMode(value: boolean) {
  current = value
  localStorage.setItem(KEY, String(value))
  apply(value)
  listeners.forEach((l) => l())
}

export function useSimpleMode(): [boolean, (v: boolean) => void] {
  const simple = useSyncExternalStore(subscribe, () => current, () => current)
  return [simple, setSimpleMode]
}
