// Utilidades de formato de tiempos de natación.

/** Segundos -> 'm:ss.cc' (o 'ss.cc' bajo el minuto). */
export function toClock(seconds: number | null | undefined, decimals = 2): string {
  if (seconds == null || Number.isNaN(seconds) || seconds < 0) return '—'
  const m = Math.floor(seconds / 60)
  const rest = seconds - m * 60
  const restStr = rest.toFixed(decimals).padStart(decimals > 0 ? 3 + decimals : 2, '0')
  return m === 0 ? rest.toFixed(decimals) : `${m}:${restStr}`
}

/** 'm:ss.cc' | 'ss.cc' -> segundos. Lanza si no es parseable. */
export function toSeconds(value: string): number {
  const raw = value.trim().replace(',', '.')
  if (!raw) throw new Error('Tiempo vacío')
  const parts = raw.split(':')
  if (parts.some((p) => p === '' || Number.isNaN(Number(p)))) {
    throw new Error(`Tiempo inválido: ${value}`)
  }
  if (parts.length === 1) return Number(parts[0])
  if (parts.length === 2) return Number(parts[0]) * 60 + Number(parts[1])
  throw new Error(`Formato no soportado: ${value}`)
}

export function tryToSeconds(value: string): number | null {
  try {
    const s = toSeconds(value)
    return Number.isFinite(s) && s > 0 ? s : null
  } catch {
    return null
  }
}

export function signed(n: number, decimals = 2): string {
  return `${n > 0 ? '+' : ''}${n.toFixed(decimals)}`
}
