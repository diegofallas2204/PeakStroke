"""Envelope científico — adaptador sobre `dominio.servicios.envolvente`.

El techo I_max y el ritmo seguro por semana los calcula el motor único desde el
paso 4 (§6.1). Aquí queda la firma vieja para los llamadores que aún no la
conocen, y desaparece con ellos.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.dominio.servicios.envolvente import envolvente_de, evento_de_referencia, nivel_de


def nearest_event(distance: int) -> int:
    return evento_de_referencia(distance)


def level_for(distance: int, current_time: float) -> str:
    return nivel_de(distance, current_time).value


@dataclass
class Envelope:
    level: str
    event: int
    i_max_total: float        # fracción del tiempo actual (techo de mejora del macro)
    safe_total_s: float       # mejora máx creíble en el macro (s)
    realistic_ceiling: float  # mejor tiempo realista al cerrar el macro (s)
    peak_week_s: float        # mejora máx fisiológica de una sola semana (s)


def science_envelope(
    distance: int,
    current_time: float,
    total_weeks: int,
    n_mac: int = 1,
    age: int | None = None,
) -> Envelope:
    env = envolvente_de(distance, current_time, total_weeks, n_mac=n_mac, edad=age)
    return Envelope(
        level=env.nivel.value, event=env.evento, i_max_total=env.i_max_total,
        safe_total_s=env.mejora_maxima_s, realistic_ceiling=env.techo_realista,
        peak_week_s=env.pico_semanal_s,
    )
