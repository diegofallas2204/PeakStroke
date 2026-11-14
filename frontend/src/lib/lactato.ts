// Leer lo que se teclea al borde de la piscina, sin pedir que se teclee bien.
//
// La hoja del entrenador del 22/09 escribía los faltantes de cinco maneras
// (vacío, `-`, `--`, `NA`, `'-'`), los números como texto, las brazadas con
// `,` o `/` y el esfuerzo como rango (`6-7`). Aquí todo eso se entiende; lo que
// no se entiende devuelve `undefined` para que el campo se marque, en vez de
// guardarse como otra cosa. El esfuerzo nunca se guarda como texto: `6-7` → 6.5.

const FALTANTE = /^(?:-+|na|n\/a|s\/d)?$/i

/** Sin espacios ni las comillas con que la hoja guardaba números como texto. */
const limpiar = (texto: string) => texto.trim().replace(/^'+|'+$/g, '').trim()

/** `null` = faltante a propósito · `undefined` = no se entiende. */
export function parsearNumero(texto: string): number | null | undefined {
  const crudo = limpiar(texto).replace(',', '.')
  if (FALTANTE.test(crudo)) return null
  const n = Number(crudo)
  return Number.isFinite(n) ? n : undefined
}

/** CR-10 con medios puntos; un rango se lee como su centro. */
export function parsearEsfuerzo(texto: string): number | null | undefined {
  const crudo = limpiar(texto).replace(/,/g, '.')
  if (FALTANTE.test(crudo)) return null
  const rango = /^(\d+(?:\.\d+)?)\s*[-–a]\s*(\d+(?:\.\d+)?)$/.exec(crudo)
  const n = rango ? (Number(rango[1]) + Number(rango[2])) / 2 : Number(crudo)
  return Number.isFinite(n) && n >= 0 && n <= 10 ? n : undefined
}

/** `31, 31,30 / 30` → [31, 31, 30, 30]. Vacío o faltante → []. */
export function parsearBrazadas(texto: string): number[] | undefined {
  const crudo = limpiar(texto)
  if (FALTANTE.test(crudo)) return []
  const partes = crudo.split(/[\s,;/]+/).filter(Boolean)
  const numeros = partes.map(Number)
  return numeros.every((n) => Number.isInteger(n) && n >= 1 && n <= 200) ? numeros : undefined
}
