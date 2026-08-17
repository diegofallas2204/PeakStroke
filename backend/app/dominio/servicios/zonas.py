"""De un ritmo de carrera a la pizarra: el ritmo y la salida de cada zona.

    zona = ritmo_carrera × factor[perfil][distancia] (+ corrección estilo) × piscina

Una prescripción son **dos** números —a qué ritmo y cada cuánto se sale—, así
que cada zona sale de aquí con su `send_off` y su `rest`. Calcularlos juntos es
lo que impide que la mitad se olvide en algún consumidor: dos series al mismo
ritmo con 5 s y con 60 s de descanso no entrenan lo mismo.
"""
from __future__ import annotations

from ..valores import Estilo, Perfil, Piscina, Zona, factores_de_zona
from ..valores.tiempo import PASO_DE_RELOJ_S, Duracion, Tiempo

# Tolerancia de visualización alrededor del objetivo de zona (solo interfaz).
TOLERANCIA_DE_ZONA = 0.01


def estilo_de(texto: str) -> Estilo:
    """El estilo, cayendo en libre si el texto no se reconoce.

    Cae en vez de reventar porque el motor lee filas ya guardadas: rechazar un
    estilo imposible es trabajo de `Prueba`, en la entrada, y hacerlo aquí
    convertiría un dato viejo en un 500 al abrir el plan.
    """
    try:
        return Estilo.desde_texto(texto)
    except ValueError:
        return Estilo.LIBRE


def piscina_de(texto: str) -> Piscina:
    """La piscina, cayendo en la de 50 m. Mismo motivo que `estilo_de`."""
    try:
        return Piscina.desde_texto(texto)
    except ValueError:
        return Piscina.LARGA


def al_reloj(segundos: float) -> float:
    """Cuadra al reloj de pared, siempre hacia arriba.

    Hacia abajo recortaría el descanso prescrito, que es como una zona se
    convierte en otra (ver `Zona`).
    """
    return Duracion(segundos).al_reloj(PASO_DE_RELOJ_S).segundos


def zonas_de(
    ritmo_carrera_100: float,
    distancia: int,
    estilo: str = "libre",
    piscina: str = "50",
    distancia_rep: int = 100,
) -> dict[str, dict[str, float] | None]:
    """Ritmo objetivo y salida de cada zona para ese ritmo de carrera.

    `min`/`max` son ±1 % alrededor del objetivo. No es ciencia: es el ancho de
    banda que la interfaz enseña. El ritmo objetivo es siempre por 100 m;
    `distancia_rep` solo cambia la salida, que es de la repetición que se nada.
    """
    perfil = Perfil.para_distancia(distancia)
    factores = factores_de_zona(perfil, distancia)
    correccion = estilo_de(estilo).correccion_tpace_s
    factor_piscina = piscina_de(piscina).factor(perfil)
    proporcion_rep = max(distancia_rep, 1) / 100.0

    salida: dict[str, dict[str, float] | None] = {}
    for zona in Zona.ordenadas():
        factor = factores.get(zona)
        if factor is None:
            salida[zona.value] = None
            continue
        objetivo = (ritmo_carrera_100 * factor + correccion) * factor_piscina
        trabajo = objetivo * proporcion_rep
        intervalo = al_reloj(trabajo + zona.descanso_para(Tiempo(trabajo)).segundos)
        salida[zona.value] = {
            "min": round(objetivo * (1 - TOLERANCIA_DE_ZONA), 2),
            "mid": round(objetivo, 2),
            "max": round(objetivo * (1 + TOLERANCIA_DE_ZONA), 2),
            # Cada cuánto sale la repetición y cuánto se descansa dentro de ese
            # ciclo. `rest` es el real tras cuadrar al reloj, no el teórico.
            "send_off": intervalo,
            "rest": round(intervalo - trabajo, 2),
            "rep_distance": distancia_rep,
        }
    return salida
