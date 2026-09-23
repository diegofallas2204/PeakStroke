// Exportación de tablas a PDF (jsPDF + autoTable).
//
// Un único constructor de documento para todas las tablas de la app: mismo
// encabezado, misma retícula, mismo pie con la fecha y el número de página. Los
// colores viajan en hexadecimal y no como `var(--color-*)`: el PDF no conoce el
// tema de la pantalla, así que un documento se imprime igual en claro y oscuro.
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import type { RowInput, UserOptions } from 'jspdf-autotable'

// Tinta del documento — pensada para papel blanco, no para el tema de la app.
const TINTA = '#0f172a'
const TINTA_DIM = '#475569'
const TINTA_TENUE = '#94a3b8'
const LINEA = '#e2e8f0'
const CABECERA = '#1e293b'

const MARGEN = 34

/** Una tabla del documento. `head` y `body` ya vienen formateados para leer. */
export interface TablaPdf {
  /** Título de la tabla. Se dibuja encima; útil cuando el PDF lleva varias. */
  caption?: string
  head: string[]
  body: RowInput[]
  /** Estilos por índice de columna: color de zona, ancho, alineación. */
  columnStyles?: UserOptions['columnStyles']
  /** Nota al pie de la tabla — la misma que la explica en pantalla. */
  note?: string
}

export interface DocumentoPdf {
  title: string
  subtitle?: string
  /** Nombre del archivo, sin extensión ni fecha (la fecha se añade sola). */
  filename: string
  tables: TablaPdf[]
}

/** jsPDF guarda la última tabla dibujada aquí, pero no lo declara en sus tipos. */
type DocConTabla = jsPDF & { lastAutoTable?: { finalY: number } }

/**
 * Arma el documento y lo descarga. Todo ocurre en el cliente: los datos ya
 * están en pantalla, así que no hay petición ni endpoint que autorizar.
 */
export function descargarPdf({ title, subtitle, filename, tables }: DocumentoPdf): void {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' }) as DocConTabla
  const ancho = doc.internal.pageSize.getWidth()
  const alto = doc.internal.pageSize.getHeight()
  const generado = new Date()

  // ── Encabezado (solo la primera página; las siguientes repiten la cabecera
  // de la tabla, que ya dice qué se está leyendo) ──
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(15)
  doc.setTextColor(TINTA)
  doc.text(title, MARGEN, 44)

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8)
  doc.setTextColor(TINTA_TENUE)
  doc.text('PeakStroke', ancho - MARGEN, 34, { align: 'right' })
  doc.text(
    generado.toLocaleDateString('es', { day: 'numeric', month: 'long', year: 'numeric' }),
    ancho - MARGEN, 45, { align: 'right' },
  )

  let y = 56
  if (subtitle) {
    doc.setFontSize(9)
    doc.setTextColor(TINTA_DIM)
    for (const linea of doc.splitTextToSize(subtitle, ancho - MARGEN * 2 - 110)) {
      doc.text(linea, MARGEN, y)
      y += 11
    }
  }
  doc.setDrawColor(LINEA)
  doc.setLineWidth(0.8)
  doc.line(MARGEN, y, ancho - MARGEN, y)
  y += 16

  // ── Tablas ──
  for (const [i, tabla] of tables.entries()) {
    if (tabla.caption) {
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(10)
      doc.setTextColor(TINTA)
      doc.text(tabla.caption, MARGEN, y)
      y += 12
    }

    autoTable(doc, {
      head: [tabla.head],
      body: tabla.body,
      startY: y,
      margin: { left: MARGEN, right: MARGEN, bottom: 40 },
      theme: 'grid',
      styles: {
        font: 'helvetica', fontSize: 7.6, cellPadding: 4,
        textColor: TINTA, lineColor: LINEA, lineWidth: 0.5, overflow: 'linebreak',
      },
      headStyles: {
        fillColor: CABECERA, textColor: '#ffffff', fontStyle: 'bold', fontSize: 7.6,
      },
      alternateRowStyles: { fillColor: '#f8fafc' },
      columnStyles: tabla.columnStyles,
    })

    y = (doc.lastAutoTable?.finalY ?? y) + 14

    if (tabla.note) {
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(7.2)
      doc.setTextColor(TINTA_TENUE)
      for (const linea of doc.splitTextToSize(tabla.note, ancho - MARGEN * 2)) {
        doc.text(linea, MARGEN, y)
        y += 9
      }
      y += 8
    }

    // Una tabla nueva que no cabe empieza en página propia; partirla por la
    // mitad de su cabecera se lee peor que dejar el hueco. Detrás de la ÚLTIMA
    // no se salta: sería una página en blanco con solo el pie.
    if (i < tables.length - 1 && y > alto - 90) {
      doc.addPage()
      y = 48
    }
  }

  // ── Pie: se escribe al final, cuando ya se sabe cuántas páginas hay ──
  const paginas = doc.getNumberOfPages()
  for (let p = 1; p <= paginas; p += 1) {
    doc.setPage(p)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.2)
    doc.setTextColor(TINTA_TENUE)
    doc.text(`Generado por PeakStroke · ${generado.toLocaleString('es')}`, MARGEN, alto - 18)
    doc.text(`Página ${p} de ${paginas}`, ancho - MARGEN, alto - 18, { align: 'right' })
  }

  doc.save(`${filename}-${fechaDeArchivo(generado)}.pdf`)
}

/** '2026-08-25' — ordena solo al listar la carpeta de descargas. */
function fechaDeArchivo(d: Date): string {
  const dos = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`
}

/** Nombre de archivo sin acentos ni espacios: 'Mariposa 100m' -> 'mariposa-100m'. */
export function slug(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}
