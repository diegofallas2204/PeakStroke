/**
 * timeFormat.ts — Utilidades de formato de tiempo para el frontend.
 * Espejo del time_utils.py del backend.
 */

/** Convierte segundos a formato mm:ss.cc → '1:05.32' */
export function formatTime(seconds: number): string {
  if (seconds < 0) return '--:--.--'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toFixed(2).padStart(5, '0')}`
}

/** Formatea el pace/100m con la unidad */
export function formatPace(seconds: number): string {
  return formatTime(seconds)
}

/** Convierte string mm:ss.cc a segundos */
export function parseTime(timeStr: string): number {
  const trimmed = timeStr.trim().replace(',', '.')
  if (trimmed.includes(':')) {
    const [m, s] = trimmed.split(':')
    return parseInt(m) * 60 + parseFloat(s)
  }
  return parseFloat(trimmed)
}

/** Delta formateado con signo */
export function formatDelta(delta: number): string {
  const sign = delta < 0 ? '-' : '+'
  return `${sign}${Math.abs(delta).toFixed(2)}s`
}
