// La tabla de la plantilla (`Tabla Medición`), compartida por el formulario y la
// ficha: mismas columnas, mismo orden y mismas columnas ocultas. Lo que cambia es
// la celda (un campo para apuntar, o el valor ya guardado).
//
// En el celular la tabla se desplaza de lado con la repetición fija a la
// izquierda, como en la hoja; ocultar las columnas que no se usan es lo que la
// hace manejable.
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Calculator, Columns3, RotateCcw } from 'lucide-react'
import { COLUMNAS, type ClaveDeColumna, type Columna, type useColumnasDeLactato } from './lactatoColumnas'

type Vista = ReturnType<typeof useColumnasDeLactato>

/** Botón «Columnas» con la lista para mostrar u ocultar cada una. */
export function SelectorDeColumnas({ vista }: { vista: Vista }) {
  const [abierto, setAbierto] = useState(false)
  const caja = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!abierto) return
    const fuera = (e: MouseEvent) => { if (!caja.current?.contains(e.target as Node)) setAbierto(false) }
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') setAbierto(false) }
    document.addEventListener('mousedown', fuera)
    document.addEventListener('keydown', tecla)
    return () => { document.removeEventListener('mousedown', fuera); document.removeEventListener('keydown', tecla) }
  }, [abierto])

  const ocultas = COLUMNAS.filter((c) => !c.fija).length - (vista.columnas.length - 1)
  return (
    <div ref={caja} className="relative">
      <button
        type="button" className="btn btn-ghost !px-2.5 !py-1.5 text-[12px]"
        aria-expanded={abierto} aria-haspopup="true" onClick={() => setAbierto(!abierto)}
        title="Mostrar u ocultar columnas"
      >
        <Columns3 size={14} /> Columnas{ocultas > 0 && <span className="text-text-faint">· {ocultas} ocultas</span>}
      </button>
      {abierto && (
        <div className="card absolute right-0 z-30 mt-1.5 w-64 p-2 shadow-2xl" role="group" aria-label="Columnas visibles">
          {COLUMNAS.map((c) => (
            <label
              key={c.clave} title={c.ayuda}
              className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-[12.5px] ${c.fija ? 'opacity-50' : 'cursor-pointer hover:bg-surface-2'}`}
            >
              <input
                type="checkbox" checked={vista.visibles.includes(c.clave)} disabled={c.fija}
                onChange={() => vista.alternar(c.clave)}
              />
              <span className="flex-1">{c.etiqueta}</span>
              {c.calculo && <Calculator size={12} className="text-text-faint" aria-label="Se calcula" />}
            </label>
          ))}
          <hr className="my-1.5 border-line" />
          <label className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-[12.5px] hover:bg-surface-2">
            <input type="checkbox" checked={vista.recuperacion} onChange={vista.alternarRecuperacion} />
            <span className="flex-1">Recuperación</span>
          </label>
          <button type="button" className="btn btn-ghost mt-1 w-full justify-center !py-1 text-[11.5px]" onClick={vista.restablecer}>
            <RotateCcw size={12} /> Las de siempre
          </button>
        </div>
      )}
    </div>
  )
}

/** La tabla: una fila por repetición; `celda` decide qué va en cada una. */
export function TablaDeLactato({
  columnas, filas, celda, marcada, pie,
}: {
  columnas: Columna[]
  filas: number
  celda: (clave: ClaveDeColumna, i: number) => ReactNode
  /** Repeticiones con aviso: el número sale en ámbar. */
  marcada?: (i: number) => boolean
  pie?: ReactNode
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr className="bg-surface-2 text-[10px] uppercase tracking-wider text-text-faint">
            <th className="sticky left-0 z-10 bg-surface-2 px-2 py-2 text-left font-semibold">Rep.</th>
            {columnas.map((c) => (
              <th key={c.clave} title={c.ayuda} className="whitespace-nowrap px-1.5 py-2 text-left font-semibold">
                <span className="flex items-center gap-1">
                  {c.calculo && <Calculator size={10} aria-label="Se calcula" />}
                  {c.etiqueta}
                </span>
                {c.unidad && <span className="block text-[9px] font-normal normal-case tracking-normal">{c.unidad}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: filas }, (_, i) => (
            <tr key={i} className="border-t border-line">
              <td className={`mono sticky left-0 z-10 bg-surface px-2 py-1 text-[11px] ${marcada?.(i) ? 'font-bold text-amber' : 'text-text-faint'}`}>
                {i + 1}
              </td>
              {columnas.map((c) => (
                <td key={c.clave} className={`px-1 py-1 ${c.calculo ? 'mono whitespace-nowrap text-text-dim' : ''}`}>
                  {celda(c.clave, i)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {pie && <tfoot className="border-t border-line-strong bg-surface-2/60">{pie}</tfoot>}
      </table>
    </div>
  )
}

/** Un número calculado, o una raya si no se puede calcular. */
export function Calculado({ valor, decimales = 2 }: { valor: number | null | undefined; decimales?: number }) {
  return <>{valor == null ? '—' : valor.toFixed(decimales)}</>
}
