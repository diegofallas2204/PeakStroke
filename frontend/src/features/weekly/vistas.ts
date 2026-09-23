// Las tres vistas del plan semanal. Catálogo único: lo consumen las pestañas
// del módulo y el parseo de `?vista=`, igual que `navConfig` es el catálogo
// único de secciones. Dos listas —una para pintar, otra para enrutar— acaban
// diciendo cosas distintas.
import { ListChecks, TrendingUp, Waves, type LucideIcon } from 'lucide-react'

export type VistaId = 'plan' | 'progresion' | 'zonas'

export type VistaDef = {
  id: VistaId
  label: string
  icon: LucideIcon
  /** Subtítulo de la cabecera: cada vista responde a una pregunta distinta. */
  subtitle: string
}

export const VISTAS: VistaDef[] = [
  {
    id: 'plan',
    label: 'Plan',
    icon: ListChecks,
    subtitle: 'Proyección del motor semana a semana: registra el tiempo real para recalcular la curva restante',
  },
  {
    id: 'progresion',
    label: 'Progresión',
    icon: TrendingUp,
    subtitle: 'Curva ideal vs. proyección ajustada vs. rendimiento real',
  },
  {
    id: 'zonas',
    label: 'Zonas',
    icon: Waves,
    subtitle: 'Ritmo objetivo y salida por zona de la semana seleccionada',
  },
]

/**
 * `?vista=` → vista.
 *
 * Un valor desconocido cae a Plan en vez de dejar la pantalla en blanco: la
 * URL la escribe cualquiera, y un marcador viejo o un dedo torpe no deberían
 * romper la sección.
 */
export function vistaDesdeParam(param: string | null): VistaId {
  return VISTAS.some((v) => v.id === param) ? (param as VistaId) : 'plan'
}
