"""`Sesion`: lo que un atleta nadó un día. Paso 7 del rediseño (`docs/REDISENO.md` §5.11).

**Es un registro de lo HECHO, no de lo mandado.** Se apunta después de nadar
—el atleta o su entrenador— con cuatro números: metros, duración, RPE y fecha.
Es la opción A que se eligió al arrancar C7 (2026-09-23): lo mínimo que
alimenta a Banister sin cambiarle la rutina al entrenador. Planificar la sesión
antes de nadarla (la nota 22 del vault) es otro módulo, y `Serie` salió del
rediseño en R1.

Qué se guarda y qué no, que es la distinción que sostiene el modelo:

    SE GUARDA (hechos)      distancia, duración, RPE, fecha, notas
    SE DERIVA (nunca se     el ritmo medio, la carga (sTSS), la semana y el
    persiste)               macrociclo en que cae

Las zonas y las prescripciones **tampoco** se guardan aquí: son derivados
deterministas del ritmo de la semana, y una copia se quedaría mintiendo en
cuanto el entrenador ajuste la meta. La única prescripción que merecería
guardarse es la fotografía de lo que se mandó nadar un día concreto
(`Serie.prescripcion` en §5.11), y esa pieza no existe.

**Sin FK a la semana ni al macrociclo**, por la misma razón que `Resultado`
(R2 enmendada, §10.2): `weekly_plans` va por prueba objetivo, así que un atleta
con dos pruebas tiene dos filas para la misma semana y `semana_id` no tendría a
cuál apuntar. La sesión cuelga del atleta y el plan la encuentra por fechas.

**Sin `zonas_nadadas()`** (estaba en §5.11): sin series no se sabe cuántos
metros se nadaron en cada zona. Lo único disponible sería el reparto
*planificado* de la semana, y presentarlo como nadado es el dato que miente.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..valores import Ritmo, Tiempo
from .base import PorIdentidad

# Escala CR-10 de Borg (1982) en su uso para la sesión entera, «session RPE»
# (Foster et al., 2001, J Strength Cond Res 15(1):109-115): 0 es reposo, 10 el
# máximo. El 0 se excluye porque una sesión nadada no es reposo.
RPE_MINIMO = 1
RPE_MAXIMO = 10

_SEGUNDOS_POR_HORA = 3600


@dataclass(slots=True, eq=False)
class Sesion(PorIdentidad):
    """Una sesión de agua de un atleta: cuánto, cuánto tardó y cuánto le costó.

    `duracion` es la **total**, descansos incluidos: de la primera salida a la
    última llegada. Es un `Tiempo` y no una `Duracion` porque es siempre
    positiva y porque el ritmo medio se deriva de ella (`Ritmo.desde` pide un
    `Tiempo`). Contar el descanso es lo que hace el sTSS de natación: la
    velocidad normalizada es la distancia entre el tiempo total de la sesión.

    Puede haber varias el mismo día (dobles): no hay nada único por
    `(atleta, fecha)`, y la carga del día es la suma.
    """

    atleta_id: int
    fecha: date
    distancia_m: int
    duracion: Tiempo
    rpe: int | None = None
    notas: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.distancia_m, bool) or not isinstance(self.distancia_m, int):
            raise TypeError(f"La distancia son metros enteros: {self.distancia_m!r}")
        if self.distancia_m <= 0:
            raise ValueError(f"Una sesión nada algo: {self.distancia_m} m")
        if not isinstance(self.duracion, Tiempo):
            raise TypeError("La duración de una sesión es un Tiempo")
        if self.rpe is not None:
            if isinstance(self.rpe, bool) or not isinstance(self.rpe, int):
                raise TypeError(f"El RPE es un entero de la escala CR-10: {self.rpe!r}")
            if not RPE_MINIMO <= self.rpe <= RPE_MAXIMO:
                raise ValueError(
                    f"El RPE va de {RPE_MINIMO} a {RPE_MAXIMO}: {self.rpe}",
                )

    def ritmo_medio(self) -> Ritmo:
        """Segundos por 100 m sobre la duración total. **Derivado, no se guarda.**

        Incluye el descanso, así que es bastante más lento que el ritmo de
        cualquier repetición de la sesión: no es un ritmo de zona y no se
        compara con uno.
        """
        return Ritmo.desde(self.duracion, self.distancia_m)

    def carga(self, css: Ritmo) -> float:
        """sTSS de la sesión. **Derivado, no se guarda.**

            IF   = CSS / ritmo_medio          (los dos en s/100 m)
            sTSS = duración_s · IF² / 3600 · 100

        Por construcción, una hora entera al CSS vale 100. El IF² recoge que el
        estrés crece de forma no lineal con la intensidad. Fuente: nota 05 del
        vault (Paincave.io 2026, adaptado de Coggan 2003).

        `css` lo elige quien llama, y no es un detalle: tiene que ser el
        vigente **el día de la sesión**, no el de hoy. Si no, un test nuevo
        reescribiría hacia atrás la carga de meses. Esa elección es de C8.
        """
        intensidad = css.segundos_por_100 / self.ritmo_medio().segundos_por_100
        return self.duracion.segundos * intensidad ** 2 / _SEGUNDOS_POR_HORA * 100
