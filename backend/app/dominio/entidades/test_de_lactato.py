"""El test de lactato: una serie con mediciones por repetición (notas 26 y 28).

**No es un `TestAerobico`, a propósito.** Su ritmo medio no es una base aeróbica:
un 10×400 en R1 sale a ≈73 s/100, y si se colara donde se lee la base
(`tests[0].avg_per100` al inscribir, y el CSS de la carga en `repositorios/
carga.py`) contaminaría el nivel, las zonas, la predicción y el sTSS —el mismo
tipo de error que la base inflada un 114 % de la nota 19—. Siendo otro agregado
con su propia tabla, no hay filtro que olvidar: no está en la lista.

Lo que se apunta es poco y opcional salvo el tiempo: lactato, FC, esfuerzo
(CR-10, con medios puntos) y los conteos de brazada del tramo que se cuenta.
**Todo lo demás se deriva aquí y nunca se teclea**: velocidad, % del propuesto y
de su mejor marca, CV y pendiente, metros por brazada, frecuencia de ciclo,
índice de brazada, deriva y estado estable. Los avisos de calidad están en
`servicios/avisos_de_lactato.py`.

Una brazada es un brazo; un ciclo son dos.
"""
from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from ..valores import (
    EstadoDeZona,
    MetodoDeFc,
    ModoDeLactato,
    SitioDeMuestra,
    Tiempo,
    TipoDeDescanso,
    Zona,
)
from .base import PorIdentidad

# Criterio de estado estable (MLSS, nota 28): el lactato no sube más de esto en
# la segunda mitad de la serie.
SUBIDA_MAXIMA_ESTABLE = 1.0

_LACTATO = (0.0, 30.0)     # mmol/L
_FC = (30, 250)            # lat/min
_ESFUERZO = (0.0, 10.0)    # CR-10
_BRAZADAS = (1, 200)       # por tramo


def _en(valor: float | None, limites: tuple[float, float], que: str) -> float | None:
    if valor is None:
        return None
    if not (limites[0] <= valor <= limites[1]) or (isinstance(valor, float) and not math.isfinite(valor)):
        raise ValueError(f"{que} fuera de rango: {valor} (entre {limites[0]} y {limites[1]})")
    return valor


@dataclass(frozen=True, slots=True)
class Repeticion:
    """Una repetición. `tiempo` es siempre el tiempo NADADO."""

    numero: int
    tiempo: Tiempo
    lactato: float | None = None
    fc: int | None = None
    esfuerzo: float | None = None
    brazadas: tuple[int, ...] = ()
    # Lo que tardó en el tramo contado. Con él la frecuencia deja de ser estimada.
    tiempo_tramo: Tiempo | None = None

    def __post_init__(self) -> None:
        if self.numero < 1:
            raise ValueError("Las repeticiones se numeran desde 1")
        if not isinstance(self.tiempo, Tiempo):
            raise TypeError("El tiempo de una repetición es un Tiempo")
        _en(self.lactato, _LACTATO, "Lactato")
        _en(self.fc, _FC, "Frecuencia cardiaca")
        _en(self.esfuerzo, _ESFUERZO, "Esfuerzo")
        object.__setattr__(self, "brazadas", tuple(int(b) for b in self.brazadas))
        for b in self.brazadas:
            _en(b, _BRAZADAS, "Conteo de brazadas")

    def brazadas_medias(self) -> float | None:
        return sum(self.brazadas) / len(self.brazadas) if self.brazadas else None

    def deriva_interna_pct(self) -> float | None:
        """Del primer al último conteo de la misma repetición, en %."""
        if len(self.brazadas) < 2:
            return None
        return (self.brazadas[-1] - self.brazadas[0]) / self.brazadas[0] * 100


@dataclass(frozen=True, slots=True)
class ProtocoloDeMuestra:
    """Cómo se midió. Sin esto las muestras no se comparan entre tests (nota 28 §5)."""

    sitio: SitioDeMuestra | None = None
    analizador: str | None = None
    minuto: float | None = None          # minuto tras la repetición
    metodo_fc: MetodoDeFc | None = None


class TestDeLactato(PorIdentidad):
    __test__ = False   # una medición del atleta, no una prueba de pytest

    __slots__ = (
        "activo", "atleta_id", "descanso", "descanso_s", "distancia_rep", "fecha", "id",
        "modo", "notas", "propuesto", "protocolo", "referencia", "repeticiones",
        "tramo_m", "zona",
    )

    def __init__(
        self, *, fecha: date, zona: Zona, distancia_rep: int,
        repeticiones: Sequence[Repeticion],
        modo: ModoDeLactato = ModoDeLactato.CONTROL,
        descanso: TipoDeDescanso | None = None, descanso_s: float | None = None,
        propuesto: tuple[float, float] | None = None, referencia: float | None = None,
        tramo_m: int | None = None, protocolo: ProtocoloDeMuestra | None = None,
        id: int | None = None, atleta_id: int | None = None,
        notas: str | None = None, activo: bool = True,
    ) -> None:
        if not repeticiones:
            raise ValueError("Se requiere al menos una repetición")
        if [r.numero for r in repeticiones] != list(range(1, len(repeticiones) + 1)):
            raise ValueError("Las repeticiones van numeradas 1, 2, 3… sin huecos")
        if distancia_rep <= 0:
            raise ValueError("La distancia de repetición debe ser positiva")
        if (descanso is None) != (descanso_s is None):
            raise ValueError("El descanso lleva su tipo (pausa o salida) y sus segundos")
        if descanso_s is not None and descanso_s <= 0:
            raise ValueError("El descanso debe ser positivo")
        if propuesto is not None:
            bajo, alto = propuesto
            if bajo <= 0 or alto < bajo:
                raise ValueError("El tiempo propuesto va de menor a mayor y es positivo")
            propuesto = (float(bajo), float(alto))
        if referencia is not None and referencia <= 0:
            raise ValueError("La marca de referencia debe ser positiva")
        if tramo_m is not None and not (0 < tramo_m <= distancia_rep):
            raise ValueError("El tramo contado cabe dentro de la repetición")
        if tramo_m is None and any(r.brazadas for r in repeticiones):
            raise ValueError("Con conteos de brazada hay que decir qué tramo se contó (en metros)")

        self.id, self.atleta_id = id, atleta_id
        self.fecha, self.zona, self.modo = fecha, zona, modo
        self.distancia_rep = int(distancia_rep)
        self.repeticiones: tuple[Repeticion, ...] = tuple(repeticiones)
        self.descanso, self.descanso_s = descanso, descanso_s
        self.propuesto, self.referencia, self.tramo_m = propuesto, referencia, tramo_m
        self.protocolo = protocolo or ProtocoloDeMuestra()
        self.notas, self.activo = notas, activo

    # ── Ritmo ────────────────────────────────────────────────────────────────

    def tiempos(self) -> list[float]:
        return [r.tiempo.segundos for r in self.repeticiones]

    def tiempo_medio(self) -> Tiempo:
        return Tiempo(statistics.fmean(self.tiempos()))

    def cv_pct(self) -> float:
        """Coeficiente de variación del tiempo (poblacional), en %."""
        return statistics.pstdev(self.tiempos()) / self.tiempo_medio().segundos * 100

    def pendiente(self) -> float:
        """Segundos que gana (−) o pierde (+) cada repetición."""
        ts = self.tiempos()
        if len(ts) < 2:
            return 0.0
        return statistics.linear_regression(range(len(ts)), ts).slope

    def velocidad(self, rep: Repeticion | None = None) -> float:
        """m/s de una repetición, o de la serie con su tiempo medio."""
        t = rep.tiempo if rep is not None else self.tiempo_medio()
        return self.distancia_rep / t.segundos

    def centro_del_propuesto(self) -> float | None:
        return sum(self.propuesto) / 2 if self.propuesto else None

    def pct_del_propuesto(self, rep: Repeticion | None = None) -> float | None:
        """Velocidad nadada / velocidad propuesta (centro del rango), en %."""
        centro = self.centro_del_propuesto()
        t = (rep.tiempo if rep is not None else self.tiempo_medio()).segundos
        return centro / t * 100 if centro else None

    def diferencia_con_propuesto(self) -> float | None:
        """Segundos de la media sobre el centro del propuesto. Negativo = más rápido."""
        centro = self.centro_del_propuesto()
        return self.tiempo_medio().segundos - centro if centro else None

    def pct_de_referencia(self, rep: Repeticion | None = None) -> float | None:
        """Velocidad nadada / la de su mejor marca en la distancia, en %."""
        t = (rep.tiempo if rep is not None else self.tiempo_medio()).segundos
        return self.referencia / t * 100 if self.referencia else None

    # ── Lactato ──────────────────────────────────────────────────────────────

    def muestras(self) -> list[tuple[int, float]]:
        return [(r.numero, r.lactato) for r in self.repeticiones if r.lactato is not None]

    def lactato_mediano(self) -> float | None:
        valores = [v for _, v in self.muestras()]
        return statistics.median(valores) if valores else None

    def estado_de_zona(self, lactato: float) -> EstadoDeZona | None:
        rango = self.zona.rango_de_lactato
        if rango is None:
            return None
        bajo, alto = rango
        if lactato < bajo:
            return EstadoDeZona.DEBAJO
        if alto is not None and lactato > alto:
            return EstadoDeZona.ENCIMA
        return EstadoDeZona.DENTRO

    def subida_en_la_segunda_mitad(self) -> float | None:
        """Última muestra menos la primera de la segunda mitad. Hace falta dos."""
        mitad = len(self.repeticiones) / 2
        segunda = [v for n, v in self.muestras() if n > mitad]
        return round(segunda[-1] - segunda[0], 3) if len(segunda) >= 2 else None

    def estado_estable(self) -> bool | None:
        """`None` si no se puede decir: pocas muestras, o test escalonado."""
        if self.modo is not ModoDeLactato.CONTROL:
            return None
        subida = self.subida_en_la_segunda_mitad()
        return None if subida is None else subida <= SUBIDA_MAXIMA_ESTABLE

    # ── Brazada ──────────────────────────────────────────────────────────────

    def con_conteo(self) -> list[Repeticion]:
        return [r for r in self.repeticiones if r.brazadas]

    def metros_por_brazada(self, rep: Repeticion) -> float | None:
        media = rep.brazadas_medias()
        return self.tramo_m / media if media and self.tramo_m else None

    def frecuencia_de_ciclo(self, rep: Repeticion) -> tuple[float | None, bool]:
        """(ciclos/min, estimada). Sin tiempo del tramo, se reparte el de la repetición.

        Estimada sobrestima a todos por igual (el tramo empieza con vuelta e
        impulso): sirve para comparar, no como valor absoluto.
        """
        media = rep.brazadas_medias()
        if not media or not self.tramo_m:
            return None, True
        if rep.tiempo_tramo is not None:
            return (media / 2) / rep.tiempo_tramo.segundos * 60, False
        tramo_s = rep.tiempo.segundos * self.tramo_m / self.distancia_rep
        return (media / 2) / tramo_s * 60, True

    def indice_de_brazada(self, rep: Repeticion | None = None) -> float | None:
        """SI = velocidad × metros por ciclo. De la serie, con las medias de toda ella."""
        if not self.tramo_m:
            return None
        if rep is not None:
            media = rep.brazadas_medias()
        else:
            medias = [r.brazadas_medias() for r in self.con_conteo()]
            media = statistics.fmean(medias) if medias else None
        if not media:
            return None
        return self.velocidad(rep) * 2 * self.tramo_m / media

    def deriva_de_brazada_pct(self) -> float | None:
        """De la primera a la última repetición con conteo, en %."""
        reps = self.con_conteo()
        if len(reps) < 2:
            return None
        primera, ultima = reps[0].brazadas_medias(), reps[-1].brazadas_medias()
        return (ultima - primera) / primera * 100   # type: ignore[operator]

    def __str__(self) -> str:
        return f"Lactato {self.zona.value} {len(self.repeticiones)}×{self.distancia_rep} ({self.fecha})"
