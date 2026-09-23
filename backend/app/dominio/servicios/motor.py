"""`MotorCientifico` — **el** motor. Uno solo (§6.1).

Hasta el paso 4 había dos, y el que el CLAUDE.md declaraba fuente de verdad no
corría: `ScienceEngine.generate_plan()` solo se llamaba desde los tests, y los
planes que se guardaban salían de `engine/progression.py`. Compartían las tablas
pero no el algoritmo, así que divergían solos — y ya lo habían hecho tres veces.

**La fusión no es quedarse con uno.** Cada mitad acertaba en cosas distintas:

    del científico       la distribución F_FASE por fase, la extensión a ritmo
                         seguro y la proyección anual
    del de progresión    el diferido del excedente semanal (modelo causal, no
                         recorte), la curva elegible, el reparto normalizado al
                         km que puso el entrenador y las fases del usuario

La ciencia de uno, la parametrización del otro: **la forma la pone la ciencia y
los límites los pone el entrenador** (R6). Lo que el motor científico hacía y ya
no hace es imponer su propio kilometraje y su macro fijo de 15 semanas; eso
sobrevive como *aviso* (`kilometraje.banda_de_aviso`) y como *recomendación*
(`Factibilidad.semanas_recomendadas`), que es lo que siempre debieron ser.

Esta clase es la fachada: el cálculo vive en los módulos de al lado —`zonas`,
`plan`, `envolvente`, `kilometraje`, `temporada`, `curvas`, `tablas`— y aquí
está la puerta por la que se entra, para que ningún consumidor tenga que saber
en cuál de los siete buscó lo que necesita.

Los tiempos van en segundos (`float`): ver la cabecera de `envolvente.py`.
"""
from __future__ import annotations

from datetime import date

from . import plan as _plan
from . import temporada as _temporada
from .envolvente import Envolvente, Factibilidad, envolvente_de, factibilidad
from .plan import COLOR_DE_FASE, SemanaGenerada, fases_por_defecto
from .tablas import PROYECCION_SPRINT_A_100, TOLERANCIA_DE_ESTADO, margen_de_confianza
from .temporada import MacroProyectado, ProyeccionAnual
from .zonas import zonas_de


class MotorCientifico:
    """Todo lo que el sistema sabe calcular sobre un plan de natación."""

    __slots__ = ()

    # ── Zonas ───────────────────────────────────────────────────────────────

    def zonas(
        self,
        ritmo_carrera_100: float,
        distancia: int,
        estilo: str = "libre",
        piscina: str = "50",
        distancia_rep: int = 100,
    ) -> dict[str, dict[str, float] | None]:
        """Ritmo objetivo y salida de cada zona, para un ritmo de carrera dado."""
        return zonas_de(ritmo_carrera_100, distancia, estilo, piscina, distancia_rep)

    # ── Techo y veredicto ───────────────────────────────────────────────────

    def envolvente(
        self, distancia: int, tiempo_actual: float, semanas: int,
        n_mac: int = 1, edad: int | None = None, base_aerobica: float | None = None,
    ) -> Envolvente:
        """Cuánto puede mejorar en ese macro, y cuánto en su semana más rápida."""
        return envolvente_de(
            distancia, tiempo_actual, semanas, n_mac=n_mac, edad=edad,
            base_aerobica=base_aerobica,
        )

    def factibilidad(
        self, distancia: int, tiempo_actual: float, tiempo_meta: float, semanas: int,
        semanas_por_micro: int = 4, n_mac: int = 1, edad: int | None = None,
        base_aerobica: float | None = None,
    ) -> Factibilidad:
        """Si la meta que puso el entrenador cabe en el techo científico."""
        return factibilidad(
            distancia, tiempo_actual, tiempo_meta, semanas,
            semanas_por_micro=semanas_por_micro, n_mac=n_mac, edad=edad,
            base_aerobica=base_aerobica,
        )

    # ── Plan ────────────────────────────────────────────────────────────────

    def generar_plan(
        self,
        distancia: int,
        tiempo_actual: float,
        tiempo_meta: float,
        semanas: int,
        km_totales: float,
        curva: str,
        inicio: date,
        semanas_por_micro: int = 4,
        fases: list[dict] | None = None,
        estilo: str = "libre",
        piscina: str = "50",
        n_mac: int = 1,
        edad: int | None = None,
        base_aerobica: float | None = None,
    ) -> list[SemanaGenerada]:
        """El plan completo, semana a semana.

        Cada tramo de `fases` lleva `name` (el del entrenador), `type` (la clave
        de `Fase`) y su rango de semanas. Sin fases, las cinco por defecto.
        """
        return _plan.generar(
            distancia, tiempo_actual, tiempo_meta, semanas, km_totales, curva, inicio,
            semanas_por_micro=semanas_por_micro, fases=fases, estilo=estilo,
            piscina=piscina, n_mac=n_mac, edad=edad, base_aerobica=base_aerobica,
        )

    def generar_extension(
        self,
        distancia: int,
        tiempo_actual: float,
        techo_realista: float,
        tiempo_meta: float,
        ritmo_seguro: float,
        n_extra: int,
        inicio: date,
        semanas_del_macro: int,
        km_semanales: float,
        estilo: str = "libre",
        piscina: str = "50",
    ) -> list[SemanaGenerada]:
        """Las semanas de después, cuando la meta supera el techo del macro."""
        return _plan.extender(
            distancia, tiempo_actual, techo_realista, tiempo_meta, ritmo_seguro,
            n_extra, inicio, semanas_del_macro, km_semanales,
            estilo=estilo, piscina=piscina,
        )

    def recalcular_desde(
        self,
        semanas: list[SemanaGenerada],
        desde_semana: int,
        tiempo_ancla: float,
        tiempo_meta: float,
        curva: str,
        distancia: int,
        deshabilitadas: set[int] | None = None,
        estilo: str = "libre",
        piscina: str = "50",
        n_mac: int = 1,
        edad: int | None = None,
        base_aerobica: float | None = None,
    ) -> list[SemanaGenerada]:
        """Reancla la curva en un tiempo real y reparte lo que queda."""
        return _plan.recalcular_desde(
            semanas, desde_semana, tiempo_ancla, tiempo_meta, curva, distancia,
            deshabilitadas=deshabilitadas, estilo=estilo, piscina=piscina,
            n_mac=n_mac, edad=edad, base_aerobica=base_aerobica,
        )

    # ── Lecturas sueltas ────────────────────────────────────────────────────

    def estado_de_rendimiento(self, tiempo_real: float, tiempo_esperado: float) -> str:
        """El nado real contra el plan: ahead | on_track | behind."""
        diff = (tiempo_real - tiempo_esperado) / tiempo_esperado
        if diff < -TOLERANCIA_DE_ESTADO:
            return "ahead"
        if diff > TOLERANCIA_DE_ESTADO:
            return "behind"
        return "on_track"

    def margen(self, semana: int) -> int:
        """± segundos de confianza de la predicción de esa semana (§20.3)."""
        return margen_de_confianza(semana)

    def ritmo_de_carrera_100(self, tiempo: float, distancia: int) -> float:
        """Ritmo /100 m REALISTA: un 50 no se sostiene al doble de distancia."""
        ingenuo = tiempo / (distancia / 100.0)
        return ingenuo * PROYECCION_SPRINT_A_100.get(distancia, 1.0)

    # ── Temporada ───────────────────────────────────────────────────────────

    def proyectar_temporada(
        self,
        tiempo_actual: float,
        distancia: int,
        n_macros: int = 3,
        edad: int | None = None,
        perfil: str | None = None,
    ) -> ProyeccionAnual:
        """`n_macros` encadenados, cada uno partiendo del techo del anterior."""
        return _temporada.proyectar(
            tiempo_actual, distancia, n_macros=n_macros, edad=edad, perfil=perfil,
        )


MOTOR = MotorCientifico()

__all__ = [
    "COLOR_DE_FASE",
    "MOTOR",
    "Envolvente",
    "Factibilidad",
    "MacroProyectado",
    "MotorCientifico",
    "ProyeccionAnual",
    "SemanaGenerada",
    "fases_por_defecto",
]
