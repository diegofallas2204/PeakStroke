// El texto de un estado vacío depende de quién lo está viendo.
//
// "Crea un macrociclo y asigna atletas" es una instrucción correcta para un
// entrenador y una pared para un atleta: no puede hacer ninguna de las dos
// cosas, la guarda de ruta le impide siquiera llegar a esas pantallas, y un
// vacío que pide algo imposible se lee como un error de la aplicación.
//
// Los estados vacíos son la feature, no el descuido: son lo primero que ve un
// atleta recién dado de alta, antes de tener un solo dato.
import { useRole } from './useSession'

/** Devuelve el texto del rol activo. */
export function useVacio(entrenador: string, atleta: string): string {
  return useRole() === 'athlete' ? atleta : entrenador
}
