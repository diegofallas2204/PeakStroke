"""Carga de entrenamiento: CTL, ATL y TSB. Paso 8 del rediseño (`docs/REDISENO.md` §6.3).

El modelo de Banister (1975) separa la respuesta al entrenamiento en un
componente lento (forma física) y uno rápido (fatiga). Validado en nadadores de
élite por Hellard et al. (2005) y Mitchell et al. (2020). Fuente de todo el
archivo: nota 05 del vault, «Modelo Banister: CTL, ATL, TSB».

**Entrada: el sTSS de cada sesión** (decidido al arrancar C8, 2026-09-23), que
calcula `Sesion.carga(css)`. La carga del día es la suma de sus sesiones y un
día sin sesión vale **0**: el modelo no distingue «descansó» de «no lo apuntó», y
se decidió no inventar la diferencia.

**Qué CSS vale cada día.** El del último test aeróbico con fecha ≤ ese día. Si
se usara el de hoy, un test nuevo reescribiría hacia atrás la carga de meses. Un
T15 se nada por encima del umbral, así que solo cuenta si no hay antes ningún
test que lo mida mejor (CSS, T30, directo). Una sesión anterior a cualquier test
no tiene CSS y **no entra**: se cuenta aparte para que se vea, en vez de sumar
un cero que parecería descanso.

Todo es función pura de sus entradas: calcular dos veces da lo mismo.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from ..entidades import Sesion
from ..valores import Ritmo

# ── Constantes (nota 05, «Constantes de tiempo») ─────────────────────────────

TAU_CTL_DIAS = 42   # forma física: vida media ≈ 14,7 días
TAU_ATL_DIAS = 7    # fatiga: vida media ≈ 2,4 días

# Peso de la carga de hoy en la media exponencial: 1 − e^(−1/τ). La nota 05
# escribe la actualización con exponenciales; la variante de TrainingPeaks usa
# 1/τ, que difiere menos de un 1,2 % para τ = 42.
_PESO_CTL = 1.0 - math.exp(-1.0 / TAU_CTL_DIAS)
_PESO_ATL = 1.0 - math.exp(-1.0 / TAU_ATL_DIAS)

# ── Umbrales de alerta (nota 05, «Criterios de sobreentrenamiento») ──────────
#
# Unificados el 2026-09-23: la nota traía tres tablas que no casaban entre sí.
# Son CONVENCIÓN DE LA PRÁCTICA (TrainingPeaks, Friel), no ciencia revisada por
# pares: el TSB no tiene umbrales validados en natación. Están en escala sTSS y
# no valen para otra medida de carga. Coinciden con el error 6 de la nota 14.

TSB_ADVERTENCIA = -25.0
TSB_PELIGRO = -40.0
DIAS_NEGATIVOS_SEGUIDOS = 14   # más de estos seguidos con TSB < 0: advertencia

# Rampa (nota 05, «Valores de referencia de CTL»): «subir el CTL más de +7 por
# semana aumenta el riesgo de lesión». Se compara la CTL de hoy con la de hace
# siete días. Misma naturaleza que los umbrales de TSB: convención de la práctica.
RAMPA_MAXIMA_CTL_SEMANAL = 7.0

# ── Arranque en equilibrio (decidido 2026-09-23, tras medirlo en C8) ─────────
#
# Empezar en CTL₀ = ATL₀ = 0 es suponer que el atleta no había entrenado nunca.
# La CTL (τ = 42) tarda ~3τ en olvidar ese cero, así que durante meses el TSB
# sale artificialmente negativo y las alertas son falsas: medido con el seed, un
# atleta que cumple su plan daba «fatiga sostenida» todas las semanas hasta el
# taper. Se arranca en cambio en el punto fijo de la recurrencia: con carga
# constante L, CTL = ATL = L. Se toma L = la carga media diaria de los primeros
# DIAS_PARA_EQUILIBRIO días (los días sin sesión cuentan 0). **Es un supuesto,
# no una medición**: que antes de apuntar nada ya entrenaba a una carga parecida.
# Dos semanas porque son dos τ de la ATL y dos microciclos enteros, así que la
# media no depende del día de la semana en que se empezó.
DIAS_PARA_EQUILIBRIO = 14

# Mientras esa media no está completa no hay alertas: la curva se enseña, pero
# «calentando».
DIAS_DE_CALENTAMIENTO = DIAS_PARA_EQUILIBRIO


# ── Tipos ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MedicionDeCss:
    """Un umbral medido: la fecha del test y su ritmo por 100 m.

    `preferente` es falso para los tests que se nadan por encima del umbral
    (T15, o uno libre): valen solo si no hay otro anterior.
    """

    fecha: date
    ritmo: Ritmo
    preferente: bool = True


@dataclass(frozen=True, slots=True)
class EstadoDeCarga:
    """CTL y ATL al cierre de un día. Una serie arranca en `estado_inicial`."""

    ctl: float = 0.0
    atl: float = 0.0

    @property
    def tsb(self) -> float:
        """TSB = CTL − ATL (nota 05). Sin las ganancias k₁/k₂: esas son del
        rendimiento modelado, no de la forma."""
        return self.ctl - self.atl

    def avanzar(self, carga: float) -> EstadoDeCarga:
        """Un día más: X_hoy = X_ayer · e^(−1/τ) + carga · (1 − e^(−1/τ))."""
        return EstadoDeCarga(
            ctl=self.ctl + (carga - self.ctl) * _PESO_CTL,
            atl=self.atl + (carga - self.atl) * _PESO_ATL,
        )


@dataclass(frozen=True, slots=True)
class DiaDeCarga:
    fecha: date
    stss: float
    ctl: float
    atl: float

    @property
    def tsb(self) -> float:
        return self.ctl - self.atl

    @property
    def estado(self) -> EstadoDeCarga:
        return EstadoDeCarga(self.ctl, self.atl)


class NivelDeAlerta(Enum):
    ADVERTENCIA = "advertencia"
    PELIGRO = "peligro"


class MotivoDeAlerta(Enum):
    TSB_BAJO = "tsb_bajo"                   # TSB < −25 (o < −40: peligro)
    FATIGA_SOSTENIDA = "fatiga_sostenida"   # TSB < 0 más de 14 días seguidos
    RAMPA = "rampa"                         # CTL sube más de 7 en una semana


@dataclass(frozen=True, slots=True)
class Alerta:
    fecha: date
    nivel: NivelDeAlerta
    motivos: tuple[MotivoDeAlerta, ...]


# ── Cálculo ──────────────────────────────────────────────────────────────────

def css_vigente(mediciones: Iterable[MedicionDeCss], fecha: date) -> Ritmo | None:
    """El umbral que regía `fecha`: el último preferente, o si no hay, el último."""
    anteriores = sorted((m for m in mediciones if m.fecha <= fecha), key=lambda m: m.fecha)
    preferentes = [m for m in anteriores if m.preferente]
    elegidas = preferentes or anteriores
    return elegidas[-1].ritmo if elegidas else None


def carga_por_dia(
    sesiones: Iterable[Sesion], mediciones: Sequence[MedicionDeCss],
) -> tuple[dict[date, float], int]:
    """`({fecha: sTSS del día}, sesiones sin CSS)`. Varias el mismo día se suman."""
    cargas: dict[date, float] = {}
    sin_css = 0
    for s in sesiones:
        css = css_vigente(mediciones, s.fecha)
        if css is None:
            sin_css += 1
            continue
        cargas[s.fecha] = cargas.get(s.fecha, 0.0) + s.carga(css)
    return cargas, sin_css


def estado_inicial(cargas: Mapping[date, float], inicio: date) -> EstadoDeCarga:
    """El equilibrio de arranque: CTL₀ = ATL₀ = carga media de los primeros días.

    Ver `DIAS_PARA_EQUILIBRIO`. El denominador es fijo: un día sin sesión dentro
    de la ventana es descanso, no un hueco que se salta.
    """
    total = sum(cargas.get(inicio + timedelta(days=i), 0.0) for i in range(DIAS_PARA_EQUILIBRIO))
    media = total / DIAS_PARA_EQUILIBRIO
    return EstadoDeCarga(media, media)


def serie(
    cargas: Mapping[date, float], desde: date, hasta: date,
    previo: EstadoDeCarga | None = None,
) -> list[DiaDeCarga]:
    """Un `DiaDeCarga` por cada día de `[desde, hasta]`, partiendo de `previo`.

    `previo` es el estado al cierre del día anterior a `desde` (sin él, 0 y 0;
    una serie real arranca en `estado_inicial`). Encadenar dos
    tramos —el segundo con el último estado del primero— da exactamente lo mismo
    que calcularlos de una vez, y en eso se apoya el recálculo incremental.
    """
    dias: list[DiaDeCarga] = []
    estado, fecha = previo or EstadoDeCarga(), desde
    while fecha <= hasta:
        carga = cargas.get(fecha, 0.0)
        estado = estado.avanzar(carga)
        dias.append(DiaDeCarga(fecha, carga, estado.ctl, estado.atl))
        fecha += timedelta(days=1)
    return dias


def alertas(dias: Sequence[DiaDeCarga], inicio_de_historia: date) -> list[Alerta]:
    """Las alertas de cada día de `dias` (consecutivos), fuera del calentamiento.

    La racha de TSB negativo y la rampa se miran dentro de `dias`: quien las
    quiera en su primer día tiene que pasar los `DIAS_NEGATIVOS_SEGUIDOS`
    anteriores (que cubren también los siete de la rampa).
    """
    fin_del_calentamiento = inicio_de_historia + timedelta(days=DIAS_DE_CALENTAMIENTO)
    ctl_de = {d.fecha: d.ctl for d in dias}
    resultado: list[Alerta] = []
    racha = 0
    for d in dias:
        racha = racha + 1 if d.tsb < 0 else 0
        if d.fecha < fin_del_calentamiento:
            continue
        motivos: list[MotivoDeAlerta] = []
        if d.tsb < TSB_ADVERTENCIA:
            motivos.append(MotivoDeAlerta.TSB_BAJO)
        if racha > DIAS_NEGATIVOS_SEGUIDOS:
            motivos.append(MotivoDeAlerta.FATIGA_SOSTENIDA)
        hace_una_semana = ctl_de.get(d.fecha - timedelta(days=7))
        if hace_una_semana is not None and d.ctl - hace_una_semana > RAMPA_MAXIMA_CTL_SEMANAL:
            motivos.append(MotivoDeAlerta.RAMPA)
        if motivos:
            nivel = NivelDeAlerta.PELIGRO if d.tsb < TSB_PELIGRO else NivelDeAlerta.ADVERTENCIA
            resultado.append(Alerta(d.fecha, nivel, tuple(motivos)))
    return resultado


class CargaAcumulada:
    """La fachada de §6.3: la serie completa de un atleta, desde cero.

    Es la definición de referencia. El recálculo incremental de la persistencia
    tiene que coincidir con ella, y hay un test que lo comprueba.
    """

    @staticmethod
    def calcular(
        sesiones: Iterable[Sesion], mediciones: Sequence[MedicionDeCss],
        hasta: date | None = None,
    ) -> tuple[list[DiaDeCarga], int]:
        """`(serie, sesiones sin CSS)`. La serie arranca el primer día con carga,
        en equilibrio (`estado_inicial`), y llega a `hasta` (por defecto, el
        último día con carga)."""
        cargas, sin_css = carga_por_dia(sesiones, mediciones)
        if not cargas:
            return [], sin_css
        inicio = min(cargas)
        return serie(cargas, inicio, hasta or max(cargas), estado_inicial(cargas, inicio)), sin_css
