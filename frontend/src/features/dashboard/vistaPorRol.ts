// Qué cambia en el dashboard según quién mira.
//
// Todo junto y en un solo sitio, en vez de repartido en `if (isAthlete)` por
// dentro de la página. Dos motivos: la diferencia entre las dos vistas se lee
// de un vistazo —y así se nota si una queda a medias— y el enlace muerto es el
// error fácil de cometer. Un atleta no llega a `/equipo` ni a `/macrociclos`:
// la guarda de ruta lo rebota, así que una tarjeta que apunte ahí es un clic
// que no lleva a ningún lado.
//
// Los DATOS ya vienen acotados por el backend (el atleta solo recibe sus filas).
// Esto es únicamente el lenguaje y a dónde llevan las cosas.

// Comparación dejó de ser una sección: es la vista Progresión dentro de Plan
// semanal. El enlace apunta a la vista final y no a `/comparacion`, que solo
// existe ya como redirect para marcadores viejos.
const PROGRESION = '/plan-semanal?vista=progresion'
// `?nueva=1` abre el formulario al llegar: Entrenamiento lo lee una vez y lo quita.
const APUNTAR_SESION = '/entrenamiento?nueva=1'

export type Vista = {
  /** Primera tarjeta: para el entrenador es cuánta gente lleva; para el atleta, cuántas pruebas tiene. */
  primeraTarjeta: { etiqueta: string; sub: (eventos: number, atletas: number) => string; a: string }
  estado: { etiqueta: string; a: string }
  desviacion: { a: string }
  semana: { a: string }
  tituloProgresion: string
  tituloTabla: (semana: number | string) => string
  /** El nombre del atleta en cada fila sobra cuando todas las filas son suyas. */
  muestraColumnaAtleta: boolean
  /** Acción principal de la cabecera. `null` = ninguna. */
  accion: { texto: string; a: string } | null
  /**
   * Lo que se hace a diario, por delante de la acción principal. Al atleta,
   * apuntar lo que nadó: dos toques desde su inicio. `null` = ninguna.
   */
  accionRapida: { texto: string; a: string } | null
  vacio: { titulo: string; pista: string; accion: { texto: string; a: string } | null }
}

const ENTRENADOR: Vista = {
  primeraTarjeta: {
    etiqueta: 'Atletas en plan',
    sub: (eventos) => `${eventos} pruebas objetivo activas`,
    a: '/equipo',
  },
  estado: { etiqueta: 'Estado del equipo', a: PROGRESION },
  desviacion: { a: PROGRESION },
  semana: { a: '/plan-semanal' },
  tituloProgresion: 'Progresión del equipo · % de mejora acumulada',
  tituloTabla: (semana) => `Estado por atleta · Semana ${semana}`,
  muestraColumnaAtleta: true,
  accion: { texto: 'Tabla del equipo', a: '/equipo' },
  accionRapida: null,
  vacio: {
    titulo: 'Sin macrociclo activo',
    pista: 'Crea tu primer macrociclo para empezar a planificar la temporada.',
    accion: { texto: 'Crear macrociclo', a: '/macrociclos' },
  },
}

const ATLETA: Vista = {
  primeraTarjeta: {
    etiqueta: 'Mis pruebas',
    sub: (eventos) => (eventos === 1 ? 'prueba objetivo activa' : 'pruebas objetivo activas'),
    a: '/plan-semanal',
  },
  estado: { etiqueta: 'Mi estado', a: PROGRESION },
  desviacion: { a: PROGRESION },
  semana: { a: '/plan-semanal' },
  tituloProgresion: 'Mi progresión · % de mejora acumulada',
  tituloTabla: (semana) => `Mis pruebas · Semana ${semana}`,
  muestraColumnaAtleta: false,
  accion: { texto: 'Ver mi plan semanal', a: '/plan-semanal' },
  accionRapida: { texto: 'Apuntar sesión', a: APUNTAR_SESION },
  vacio: {
    titulo: 'Todavía no estás en ningún macrociclo',
    // El macro no es algo que el atleta pueda resolver por su cuenta, así que
    // no hay botón para eso. Sí para apuntar lo que nadó: las sesiones cuelgan
    // del atleta, no del macrociclo, y cuentan aunque no esté en ninguno.
    pista: 'Cuando tu entrenador te inscriba en uno, aquí verás tu plan y tu progresión. Mientras tanto, puedes apuntar lo que nadas.',
    accion: { texto: 'Apuntar sesión', a: APUNTAR_SESION },
  },
}

export function vistaPara(role: string | null | undefined): Vista {
  return role === 'athlete' ? ATLETA : ENTRENADOR
}
