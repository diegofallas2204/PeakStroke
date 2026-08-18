"""Lo que se escribe en la pizarra: ritmo, trabajo, descanso y salida por zona.

    10 × 100  a 1:18  salida 1:30
                ^^^^         ^^^^
                ritmo        intervalo de salida

El sistema calculó el primero desde siempre y no el segundo, así que la tabla
del equipo decía a qué ritmo nadar pero no cada cuánto salir — que es la mitad
que gobierna el sistema energético que se estimula. Dos series al mismo ritmo
con 5 s y con 60 s de descanso no entrenan lo mismo.

De dónde sale cada número: el descanso es un **ratio sobre el trabajo** (no
segundos fijos: un 100 y un 400 de la misma zona no descansan lo mismo) con
suelo y techo, y todo eso vive en `valores.Zona`. La salida se cuadra al reloj
de pared **hacia arriba**, porque hacia abajo recortaría el descanso prescrito,
que es como una zona se convierte en otra.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..valores import Zona
from ..valores.tiempo import Tiempo
from .zonas import al_reloj


@dataclass(frozen=True, slots=True)
class IntervaloDeEntrenamiento:
    """Una línea de la pizarra, para una zona y una distancia de repetición."""

    zona: str
    ritmo_100: float          # ritmo objetivo de la zona, s/100 m
    trabajo: float            # tiempo de nado de la repetición, s
    descanso: float           # descanso real hasta la siguiente salida, s
    salida: float             # trabajo + descanso, cuadrado al reloj
    ratio_descanso: float     # descanso / trabajo, ya aplicados los topes
    # Comparación contra la densidad que el atleta demostró en su test, cuando
    # el test la registró. `None` en los tests antiguos, que no la tienen.
    salida_medida: float | None = None
    mas_denso_que_lo_medido: bool | None = None


def intervalos_de_entrenamiento(
    ritmos_por_zona: dict[str, float | None],
    distancia_rep: int = 100,
    *,
    ratio_medido: float | None = None,
) -> dict[str, IntervaloDeEntrenamiento]:
    """Intervalo de salida por zona para repeticiones de `distancia_rep` metros.

    `ritmos_por_zona` son los ritmos objetivo en s/100 m que ya produce
    `zonas_de` (su campo `mid`). Una zona con ritmo `None` no aplica a esa
    prueba y se omite: es lo mismo que hace `zonas_de`.

    `ratio_medido` es el descanso:trabajo que el atleta sostuvo en su test
    aeróbico. Cuando viene, cada zona añade cuál sería su salida a esa densidad
    y si la prescrita aprieta más. **No altera la prescripción**: la densidad de
    un test de umbral no es la que toca en una serie de velocidad, y dejarla
    mandar convertiría una referencia en una regla.
    """
    if distancia_rep <= 0:
        raise ValueError("La distancia de repetición debe ser positiva")

    proporcion = distancia_rep / 100.0
    salida: dict[str, IntervaloDeEntrenamiento] = {}
    for zona in Zona.ordenadas():
        ritmo = ritmos_por_zona.get(zona.value)
        if ritmo is None:
            continue
        # El trabajo se redondea ANTES de calcular el descanso: es el número que
        # el entrenador lee en la pizarra, y el descanso tiene que cuadrar con él.
        trabajo = round(ritmo * proporcion, 2)
        descanso = zona.descanso_para(Tiempo(trabajo)).segundos
        intervalo = al_reloj(trabajo + descanso)
        medida = al_reloj(trabajo * (1 + ratio_medido)) if ratio_medido is not None else None

        salida[zona.value] = IntervaloDeEntrenamiento(
            zona=zona.value,
            ritmo_100=round(ritmo, 2),
            trabajo=trabajo,
            descanso=round(intervalo - trabajo, 2),
            salida=intervalo,
            ratio_descanso=round(descanso / trabajo, 4) if trabajo else 0.0,
            salida_medida=medida,
            mas_denso_que_lo_medido=None if medida is None else intervalo < medida,
        )
    return salida
