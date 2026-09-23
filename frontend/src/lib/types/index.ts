// Tipos espejo de los schemas Pydantic del backend, repartidos por módulo.
//
// Este barril reexporta los siete: quien importa sigue escribiendo
// `from '../../lib/types'` y no le consta que el archivo se partiera.

export * from './swimmers'
export * from './identity'
export * from './plans'
export * from './zones'
export * from './aerobic'
export * from './simulator'
export * from './dashboard'
