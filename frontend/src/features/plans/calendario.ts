// Lo que el backend exige al calendario de un macrociclo (TODO-24), comprobado
// antes de enviar para que el entrenador no reciba un 422 al final del
// asistente. La regla vive en el dominio (`calendario_del_macro.py`); esto es su
// espejo y devuelve la primera razón, o `null` si cabe.
//
// Las fases cubren de la semana 1 a la última sin solaparse ni dejar huecos, en
// cualquier orden; cada competencia cae dentro del macro.

interface Tramo { name: string; week_start: number; week_end: number }
interface Cita { name: string; week_number: number }

// Los blancos de `str.strip()` de Python, que es lo que mira el backend. El `\s`
// de JS no es el mismo conjunto (no tiene \x1c-\x1f ni \x85, y sí \ufeff): con
// `trim()` un nombre podía pasar aquí y dar 422 al crear, o al revés.
// eslint-disable-next-line no-control-regex -- - son blancos para Python, y es a propósito
const BLANCOS = /^[\t\n\v\f\r\x1c-\x1f \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/

export function enBlanco(texto: string): boolean {
  return BLANCOS.test(texto)
}

export function problemaDelCalendario(fases: Tramo[], competencias: Cita[], semanas: number): string | null {
  for (const f of fases) {
    if (enBlanco(f.name)) return 'Cada fase necesita un nombre.'
    if (!Number.isInteger(f.week_start) || !Number.isInteger(f.week_end)) return `Las semanas de «${f.name}» tienen que ser números enteros.`
    if (f.week_end < f.week_start) return `La fase «${f.name}» acaba antes de empezar.`
    if (f.week_start < 1 || f.week_end > semanas) return `La fase «${f.name}» se sale de las ${semanas} semanas.`
  }
  if (fases.length > 0) {
    const ordenadas = [...fases].sort((a, b) => a.week_start - b.week_start)
    let siguiente = 1
    for (const f of ordenadas) {
      if (f.week_start < siguiente) return `La fase «${f.name}» se solapa con la anterior en la semana ${f.week_start}.`
      if (f.week_start > siguiente) return `Ninguna fase cubre de la semana ${siguiente} a la ${f.week_start - 1}.`
      siguiente = f.week_end + 1
    }
    if (siguiente <= semanas) return `Las fases acaban en la semana ${siguiente - 1}; el macrociclo llega a la ${semanas}.`
  }
  const fuera = competencias.find((c) => !Number.isInteger(c.week_number) || c.week_number < 1 || c.week_number > semanas)
  if (fuera) return `La competencia «${fuera.name || 'sin nombre'}» cae fuera de las ${semanas} semanas.`
  return null
}
