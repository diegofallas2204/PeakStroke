"""La inscripción: un atleta dentro de un macrociclo, con su base de partida.

§5.6 de `docs/REDISENO.md`, construida en C9 (2026-10-05). Hasta entonces era
solo la fila `AthletePlan`, y sacarla o devolverla era un `ap.is_active = …`
escrito en `api/v1/macrociclos/nomina.py`.

Se crea con `Macrociclo.inscribir()`, no a mano: es el macrociclo quien sabe a
quién puede admitir. **La regla «un atleta, un macrociclo vivo» no está aquí**
(decisión del usuario, 2026-10-05): necesita leer las inscripciones de todo el
equipo, y vive explicada en `api/v1/macrociclos/inscripcion.py`.

Sus pruebas son `PruebaObjetivo` (§5.7) y se guardan con ella, en la misma
transacción; no viajan dentro de este objeto, que lleva solo lo que es de la
inscripción. Las semanas todavía son filas (§5.8, punto 4 de C9).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..valores import Ritmo
from .base import PorIdentidad


class InscripcionImposible(ValueError):
    """Ese atleta no puede entrar en ese macrociclo. El mensaje es el del 409."""


@dataclass(slots=True, eq=False)
class Inscripcion(PorIdentidad):
    """El vínculo atleta ↔ macrociclo. Darla de baja no borra su histórico."""

    atleta_id: int
    macrociclo_id: int | None = None
    # Del test aeróbico, si la inscripción lo trae: el dato con el que el motor
    # fija el nivel del atleta (defecto 1 de §10.4).
    base_aerobica: Ritmo | None = None
    fuente_de_base: str | None = None   # t30 | t15 | css | manual
    activa: bool = True
    id: int | None = None

    # Idempotentes y devuelven si cambiaron, como `Atleta` (decisión del usuario,
    # 2026-10-05): sacar a quien ya está fuera no es un error, y quien llama
    # audita solo el cambio.

    def dar_de_baja(self) -> bool:
        """Saca al atleta del macrociclo. `True` si estaba dentro."""
        cambia = self.activa
        self.activa = False
        return cambia

    def restaurar(self) -> bool:
        """Lo devuelve, con su histórico intacto. `True` si estaba fuera."""
        cambia = not self.activa
        self.activa = True
        return cambia
