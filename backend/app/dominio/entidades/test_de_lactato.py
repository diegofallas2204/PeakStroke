"""El test de lactato: la plantilla del entrenador, con lo derivado calculado.

**No es un `TestAerobico`, a propósito.** Su ritmo medio no es una base aeróbica:
un 10×400 en R1 sale a ≈73 s/100, y si se colara donde se lee la base
(`tests[0].avg_per100` al inscribir, y el CSS de la carga en `repositorios/
carga.py`) contaminaría el nivel, las zonas, la predicción y el sTSS —el mismo
tipo de error que la base inflada un 114 % de la nota 19—. Siendo otro agregado
con su propia tabla, no hay filtro que olvidar: no está en la lista.

Sigue la plantilla `Tabla Medición` (2026-11-16). Se apunta lo que la hoja pide a
mano; las columnas que la hoja dejaba en blanco porque son cálculos —velocidad,
frecuencia de ciclo, efectividad por ciclo, metros por brazada, tiempo promedio,
intensidad (%)— salen de aquí y **nunca se teclean**. La lectura de los números
está en `servicios/lectura_de_lactato.py`; los avisos de calidad, en
`servicios/avisos_de_lactato.py`.

Una brazada es un brazo; un ciclo son dos. Índice de ciclo (Costill, 1985) =
velocidad × longitud de ciclo.
"""
from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import date

from ..valores import EstadoDeZona, Estilo, ModoDeLactato, Tiempo, TipoDeDescanso, Zona
from .base import PorIdentidad
from .partes_del_lactato import MuestraDeRecuperacion, ProtocoloDeMuestra, Repeticion

# Criterio de estado estable (MLSS, nota 28): el lactato no sube más de esto en
# la segunda mitad de la serie.
SUBIDA_MAXIMA_ESTABLE = 1.0


def _rango(par: tuple[float, float] | None, que: str) -> tuple[float, float] | None:
    if par is None:
        return None
    bajo, alto = par
    if bajo <= 0 or alto < bajo:
        raise ValueError(f"{que} va de menor a mayor y es positivo")
    return float(bajo), float(alto)


def _estado(valor: float, rango: tuple[float, float | None]) -> EstadoDeZona:
    bajo, alto = rango
    if valor < bajo:
        return EstadoDeZona.DEBAJO
    if alto is not None and valor > alto:
        return EstadoDeZona.ENCIMA
    return EstadoDeZona.DENTRO


class TestDeLactato(PorIdentidad):
    __test__ = False   # una medición del atleta, no una prueba de pytest

    __slots__ = (
        "activo", "atleta_id", "descanso", "descanso_s", "distancia_rep", "estilo", "fecha",
        "id", "intensidad_propuesta", "modo", "notas", "piscina_m", "propuesto", "protocolo",
        "recuperacion", "referencia", "repeticiones", "tramo_m", "zona",
    )

    def __init__(
        self, *, fecha: date, zona: Zona, distancia_rep: int,
        repeticiones: Sequence[Repeticion],
        modo: ModoDeLactato = ModoDeLactato.CONTROL,
        descanso: TipoDeDescanso | None = None, descanso_s: float | None = None,
        propuesto: tuple[float, float] | None = None, referencia: float | None = None,
        intensidad_propuesta: tuple[float, float] | None = None,
        estilo: Estilo | None = None, piscina_m: int | None = None,
        tramo_m: int | None = None, protocolo: ProtocoloDeMuestra | None = None,
        recuperacion: Sequence[MuestraDeRecuperacion] = (),
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
        propuesto = _rango(propuesto, "El tiempo propuesto")
        intensidad_propuesta = _rango(intensidad_propuesta, "La intensidad propuesta")
        if intensidad_propuesta and intensidad_propuesta[1] > 150:
            raise ValueError("La intensidad propuesta es un % de su mejor marca")
        if referencia is not None and referencia <= 0:
            raise ValueError("La marca de referencia debe ser positiva")
        if piscina_m is not None and piscina_m not in (25, 50):
            raise ValueError("La piscina es de 25 o de 50 m")
        if tramo_m is not None and not (0 < tramo_m <= distancia_rep):
            raise ValueError("El tramo contado cabe dentro de la repetición")
        if tramo_m is None and any(r.brazadas for r in repeticiones):
            raise ValueError("Con conteos de brazada hay que decir qué tramo se contó (en metros)")
        minutos = [m.minuto for m in recuperacion]
        if minutos != sorted(set(minutos)):
            raise ValueError("Los minutos de recuperación van en orden y sin repetirse")

        self.id, self.atleta_id = id, atleta_id
        self.fecha, self.zona, self.modo = fecha, zona, modo
        self.distancia_rep = int(distancia_rep)
        self.repeticiones: tuple[Repeticion, ...] = tuple(repeticiones)
        self.descanso, self.descanso_s = descanso, descanso_s
        self.propuesto, self.referencia, self.tramo_m = propuesto, referencia, tramo_m
        self.intensidad_propuesta = intensidad_propuesta
        self.estilo, self.piscina_m = estilo, piscina_m
        self.protocolo = protocolo or ProtocoloDeMuestra()
        self.recuperacion: tuple[MuestraDeRecuperacion, ...] = tuple(recuperacion)
        self.notas, self.activo = notas, activo

    # ── Ritmo e intensidad ───────────────────────────────────────────────────

    def tiempos(self) -> list[float]:
        return [r.tiempo.segundos for r in self.repeticiones]

    def tiempo_medio(self) -> Tiempo:
        """El «Tiempo promedio» del pie de la plantilla."""
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

    def propuesto_efectivo(self) -> tuple[float, float] | None:
        """El apuntado; si falta, el que sale de la intensidad propuesta y su marca.

        La hoja del 22/09 dejó el «Tiempo Pro» vacío en un atleta: la app lo
        calcula con su marca en vez de dejar la columna sin comparar.
        """
        if self.propuesto is not None:
            return self.propuesto
        if self.intensidad_propuesta and self.referencia:
            bajo, alto = self.intensidad_propuesta
            return self.referencia / (alto / 100), self.referencia / (bajo / 100)
        return None

    def centro_del_propuesto(self) -> float | None:
        propuesto = self.propuesto_efectivo()
        return sum(propuesto) / 2 if propuesto else None

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
        """La «Intensidad (%)»: velocidad nadada / la de su mejor marca."""
        t = (rep.tiempo if rep is not None else self.tiempo_medio()).segundos
        return self.referencia / t * 100 if self.referencia else None

    def estado_de_intensidad(self) -> EstadoDeZona | None:
        """La intensidad real frente a la «Intens. Pro» de la cabecera."""
        real = self.pct_de_referencia()
        if real is None or self.intensidad_propuesta is None:
            return None
        return _estado(real, self.intensidad_propuesta)

    # ── Lactato ──────────────────────────────────────────────────────────────

    def muestras(self) -> list[tuple[int, float]]:
        return [(r.numero, r.lactato) for r in self.repeticiones if r.lactato is not None]

    def lactato_mediano(self) -> float | None:
        valores = [v for _, v in self.muestras()]
        return statistics.median(valores) if valores else None

    def estado_de_zona(self, lactato: float) -> EstadoDeZona | None:
        rango = self.zona.rango_de_lactato
        return _estado(lactato, rango) if rango is not None else None

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

    # ── Recuperación ─────────────────────────────────────────────────────────

    def pico_de_recuperacion(self) -> tuple[float, float] | None:
        """(minuto, mmol/L) del lactato más alto tras la serie."""
        con_lactato = [(m.minuto, m.lactato) for m in self.recuperacion if m.lactato is not None]
        return max(con_lactato, key=lambda p: p[1]) if con_lactato else None

    def aclaramiento_pct(self) -> float | None:
        """Cuánto bajó el lactato desde el pico hasta la última muestra, en %."""
        pico = self.pico_de_recuperacion()
        despues = [m for m in self.recuperacion if m.lactato is not None and pico and m.minuto > pico[0]]
        if not pico or not despues:
            return None
        return (pico[1] - despues[-1].lactato) / pico[1] * 100   # type: ignore[operator]

    def tasa_de_aclaramiento(self) -> float | None:
        """mmol/L que baja por minuto desde el pico."""
        pico = self.pico_de_recuperacion()
        despues = [m for m in self.recuperacion if m.lactato is not None and pico and m.minuto > pico[0]]
        if not pico or not despues:
            return None
        return (pico[1] - despues[-1].lactato) / (despues[-1].minuto - pico[0])   # type: ignore[operator]

    # ── Brazada ──────────────────────────────────────────────────────────────

    def con_conteo(self) -> list[Repeticion]:
        return [r for r in self.repeticiones if r.brazadas]

    def metros_por_brazada(self, rep: Repeticion) -> float | None:
        media = rep.brazadas_medias()
        return self.tramo_m / media if media and self.tramo_m else None

    def metros_por_ciclo(self, rep: Repeticion) -> float | None:
        """La «Efectividad por ciclo» de la plantilla: la longitud de ciclo."""
        mpb = self.metros_por_brazada(rep)
        return 2 * mpb if mpb else None

    def frecuencia_de_ciclo(self, rep: Repeticion) -> tuple[float | None, bool]:
        """(ciclos/min, estimada).

        Real con el tiempo del tramo. Si no, se estima: con los parciales (cada
        conteo cae en uno; el tramo es su parte proporcional), o repartiendo el
        tiempo de la repetición. La estimación sobrestima a todos por igual (el
        tramo empieza con vuelta e impulso): sirve para comparar.
        """
        media = rep.brazadas_medias()
        if not media or not self.tramo_m:
            return None, True
        ciclos = media / 2
        if rep.tiempo_tramo is not None:
            return ciclos / rep.tiempo_tramo.segundos * 60, False
        if rep.parciales:
            tramo_de_parcial = self.distancia_rep / len(rep.parciales)
            tramo_s = statistics.fmean(rep.parciales) * self.tramo_m / tramo_de_parcial
            return ciclos / tramo_s * 60, True
        tramo_s = rep.tiempo.segundos * self.tramo_m / self.distancia_rep
        return ciclos / tramo_s * 60, True

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
