// Las columnas de la plantilla del entrenador (`Tabla Medición`), en su orden.
//
// La hoja real dejaba columnas enteras sin llenar —la FC en 7 de 16 atletas,
// la serie y los parciales en todos—, así que cada una se puede ocultar. Las de
// cálculo (velocidad, frecuencia de ciclo, efectividad, metros por brazada) las
// rellena la app: en la hoja estaban vacías porque nadie las calculaba a mano.
//
// Lo que cada quien oculta se recuerda en su navegador: es una comodidad de
// quien mira, no un dato del test.
import { useState } from 'react'
import type { EstadoDeZona } from '../../lib/types'

/** Dentro, por debajo o por encima del rango: el color con que se pinta. */
export const COLOR_DE_ESTADO: Record<EstadoDeZona, string> = {
  dentro: '#34d399', debajo: '#60a5fa', encima: '#fb7185',
}

export type ClaveDeColumna =
  | 'serie' | 'tiempo' | 'intensidad' | 'velocidad' | 'lactato' | 'fc'
  | 'frecuencia' | 'brazadas' | 'efectividad' | 'metros' | 'parciales' | 'tramo'

export interface Columna {
  clave: ClaveDeColumna
  etiqueta: string
  unidad?: string
  ayuda: string
  calculo: boolean
  /** El tiempo no se oculta: sin él no hay repetición. */
  fija?: boolean
  porDefecto: boolean
}

export const COLUMNAS: Columna[] = [
  { clave: 'serie', etiqueta: 'Serie', ayuda: 'Número de serie, si el test tiene varias', calculo: false, porDefecto: false },
  { clave: 'tiempo', etiqueta: 'Tiempo', ayuda: 'Tiempo nadado de la repetición', calculo: false, fija: true, porDefecto: true },
  { clave: 'intensidad', etiqueta: 'Intensidad', unidad: '1–10', ayuda: 'Esfuerzo percibido (CR-10). «6-7» se guarda como 6.5', calculo: false, porDefecto: true },
  { clave: 'velocidad', etiqueta: 'Velocidad', unidad: 'm/s', ayuda: 'Distancia ÷ tiempo', calculo: true, porDefecto: true },
  { clave: 'lactato', etiqueta: 'Lactato', unidad: 'mmol/L', ayuda: 'Muestra tras la repetición', calculo: false, porDefecto: true },
  { clave: 'fc', etiqueta: 'FC', unidad: 'lat/min', ayuda: 'Frecuencia cardiaca tras la repetición', calculo: false, porDefecto: true },
  { clave: 'frecuencia', etiqueta: 'Frec. ciclo', unidad: 'ciclos/min', ayuda: 'Ciclos (2 brazadas) por minuto en el tramo contado. Estimada salvo con el tiempo del tramo', calculo: true, porDefecto: true },
  { clave: 'brazadas', etiqueta: 'Brazadas', ayuda: 'Conteos del tramo, separados por coma o barra', calculo: false, porDefecto: true },
  { clave: 'efectividad', etiqueta: 'Efect. ciclo', unidad: 'm', ayuda: 'Metros que avanza cada ciclo (longitud de ciclo)', calculo: true, porDefecto: true },
  { clave: 'metros', etiqueta: 'Metros brazada', unidad: 'm', ayuda: 'Metros por brazada (un brazo)', calculo: true, porDefecto: true },
  { clave: 'parciales', etiqueta: 'Parciales', ayuda: 'Tiempos de cada tramo igual (p. ej. los 4 × 100 de un 400)', calculo: false, porDefecto: false },
  { clave: 'tramo', etiqueta: 'Tiempo del tramo', ayuda: 'Lo que tardó en el tramo contado: hace real la frecuencia', calculo: false, porDefecto: false },
]

const CLAVE_LOCAL = 'peakstroke.lactato.columnas'
const CLAVE_RECUPERACION = 'peakstroke.lactato.recuperacion'

function leer<T>(clave: string, porDefecto: T): T {
  try {
    const crudo = localStorage.getItem(clave)
    return crudo ? (JSON.parse(crudo) as T) : porDefecto
  } catch {
    return porDefecto
  }
}

function guardar(clave: string, valor: unknown) {
  try {
    localStorage.setItem(clave, JSON.stringify(valor))
  } catch {
    // Sin almacenamiento (ventana privada): se recuerda solo mientras dure la página.
  }
}

const VISIBLES_POR_DEFECTO = COLUMNAS.filter((c) => c.porDefecto).map((c) => c.clave)

/** Qué columnas se ven y si se ve el bloque de recuperación. */
export function useColumnasDeLactato() {
  const [visibles, setVisibles] = useState<ClaveDeColumna[]>(() => {
    const guardadas = leer<ClaveDeColumna[]>(CLAVE_LOCAL, VISIBLES_POR_DEFECTO)
    // Las fijas siempre; una clave que ya no existe, fuera.
    return COLUMNAS.filter((c) => c.fija || guardadas.includes(c.clave)).map((c) => c.clave)
  })
  const [recuperacion, setRecuperacion] = useState<boolean>(() => leer(CLAVE_RECUPERACION, true))

  const alternar = (clave: ClaveDeColumna) => {
    if (COLUMNAS.find((c) => c.clave === clave)?.fija) return
    setVisibles((v) => {
      const siguiente = v.includes(clave) ? v.filter((k) => k !== clave) : [...v, clave]
      guardar(CLAVE_LOCAL, siguiente)
      return siguiente
    })
  }
  const alternarRecuperacion = () => setRecuperacion((r) => {
    guardar(CLAVE_RECUPERACION, !r)
    return !r
  })
  const restablecer = () => {
    setVisibles(VISIBLES_POR_DEFECTO)
    guardar(CLAVE_LOCAL, VISIBLES_POR_DEFECTO)
  }

  return {
    columnas: COLUMNAS.filter((c) => visibles.includes(c.clave)),
    visibles, alternar, recuperacion, alternarRecuperacion, restablecer,
  }
}
