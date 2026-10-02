// Utilidades de formato: tiempos de natación y presentación de nombres/fechas.

/** 'Sofía Ramírez' -> 'SR'. Para los avatares de atletas y cuentas. */
export function initials(name: string): string {
  return name.split(' ').slice(0, 2).map((p) => p[0]).join('').toUpperCase()
}

/** ISO -> '3 ago 2026'. Devuelve '—' si no hay fecha. */
export function toShortDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })
}


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

/** Segundos -> 'h:mm' ('0:45', '1:30'). Para duraciones de sesión. */
export function toHoursMinutes(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds < 0) return '—'
  const totalMin = Math.round(seconds / 60)
  return `${Math.floor(totalMin / 60)}:${String(totalMin % 60).padStart(2, '0')}`
}

/**
 * 'h:mm' -> segundos; un número suelto se lee como MINUTOS ('90' = 1:30).
 * `null` si no es una duración positiva. Los minutos de 'h:mm' van de 0 a 59:
 * '1:75' es un error de tecleo, no una hora y tres cuartos.
 */
export function parseHoursMinutes(value: string): number | null {
  const raw = value.trim()
  if (/^\d+$/.test(raw)) {
    const min = Number(raw)
    return min > 0 ? min * 60 : null
  }
  const m = /^(\d+):(\d{1,2})$/.exec(raw)
  if (!m) return null
  const [h, min] = [Number(m[1]), Number(m[2])]
  if (min > 59) return null
  const total = (h * 60 + min) * 60
  return total > 0 ? total : null
}

/** Fecha local -> 'YYYY-MM-DD', sin pasar por UTC (que de noche da mañana). */
export function isoDay(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

/** 'YYYY-MM-DD' -> '3 ago'. Para ejes y listas donde el año sobra. */
export function toDayMonth(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('es', { day: 'numeric', month: 'short' })
}

/** 'YYYY-MM-DD' -> 'DD/MM'. El formato de fecha de los ejes (CLAUDE.md). */
export function toDDMM(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${d}/${m}`
}
