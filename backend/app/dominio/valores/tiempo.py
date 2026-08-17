"""Tiempo, ritmo y mejora — las tres cantidades del rendimiento, con su unidad.

Hoy ocho columnas `float` mezclan dos unidades: `current_time`, `goal_time`,
`expected_time`, `recalc_time` y `real_time` son segundos absolutos; `avg_per100`,
`css_ms` y `pace_100m` son segundos por 100 m. Nada impide restar un ritmo de un
tiempo y obtener un número que parece correcto (REDISENO §3.1, hallazgo P6).

`Tiempo` y `Ritmo` son tipos **distintos** a propósito: no comparten operadores,
así que esa resta deja de escribirse. La conversión entre ellos existe, pero hay
que pedirla y hay que decir con qué distancia — que es exactamente el dato que
falta cuando alguien los mezcla.

`Mejora` existe porque los dos motores actuales expresan lo mismo de dos formas:
`engine/progression.py` maneja segundos y `ScienceEngine` maneja fracciones
decimales. Un tipo que lleva las dos elimina la conversión repetida a mano.

Sustituye a `app/engine/time_utils.py` (§8 del mapa de traducción); mientras dure
la transición conviven, y `tests/test_valores_vs_motor.py` fija que dan lo mismo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Manecilla del reloj de pared de la piscina: se lee en múltiplos de 5 s.
PASO_DE_RELOJ_S = 5.0


def _formatear(segundos: float, decimales: int = 2) -> str:
    """`65.32 → '1:05.32'` · `45.1 → '45.10'` (mismo formato que `to_clock`)."""
    minutos = int(segundos // 60)
    resto = segundos - minutos * 60
    if minutos == 0:
        return f"{resto:.{decimales}f}"
    ancho = 3 + decimales if decimales > 0 else 2
    return f"{minutos}:{resto:0{ancho}.{decimales}f}"


def _parsear(texto: str) -> float:
    """`'1:05.32' → 65.32`. Acepta coma decimal y horas (mismo que `to_seconds`)."""
    crudo = str(texto).strip().replace(",", ".")
    if not crudo:
        raise ValueError("Tiempo vacío")
    partes = crudo.split(":")
    if len(partes) == 1:
        return float(partes[0])
    if len(partes) == 2:
        return float(partes[0]) * 60.0 + float(partes[1])
    if len(partes) == 3:
        return float(partes[0]) * 3600.0 + float(partes[1]) * 60.0 + float(partes[2])
    raise ValueError(f"Formato de tiempo no reconocido: {texto!r}")


def _positivo_finito(valor: float, que: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{que} tiene que ser un número, no {type(valor).__name__}")
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{que} tiene que ser finito, no {valor!r}")
    if numero <= 0:
        raise ValueError(f"{que} tiene que ser positivo: {numero}")
    return numero


@dataclass(frozen=True, slots=True, order=True)
class Tiempo:
    """Segundos absolutos: lo que tarda alguien en nadar una distancia."""

    segundos: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "segundos", _positivo_finito(self.segundos, "Un tiempo"))

    @classmethod
    def desde_texto(cls, texto: str) -> Tiempo:
        return cls(_parsear(texto))

    def texto(self, decimales: int = 2) -> str:
        return _formatear(self.segundos, decimales)

    def a_ritmo(self, distancia: int) -> Ritmo:
        return Ritmo.desde(self, distancia)

    def al_reloj(self, paso: float = PASO_DE_RELOJ_S) -> Tiempo:
        """Redondea **hacia arriba** al múltiplo de `paso` (5 s por defecto).

        Hacia abajo recortaría el descanso prescrito, que es como una zona se
        convierte en otra (ver `Zona`).
        """
        if paso <= 0:
            raise ValueError("El paso del reloj tiene que ser positivo")
        return Tiempo(math.ceil(self.segundos / paso - 1e-9) * paso)

    def __sub__(self, otro: Tiempo) -> Mejora:
        """`inicial - final` → la `Mejora` que va de uno a otro.

        Positiva cuando el segundo es más rápido, que es como se lee en natación:
        bajar el tiempo es mejorar. La base es `self`, el tiempo de partida.
        """
        if not isinstance(otro, Tiempo):
            return NotImplemented
        return Mejora(self.segundos - otro.segundos, self.segundos)

    def __str__(self) -> str:
        return self.texto()


@dataclass(frozen=True, slots=True, order=True)
class Ritmo:
    """Segundos por 100 m. La unidad central de todos los cálculos de zonas."""

    segundos_por_100: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "segundos_por_100", _positivo_finito(self.segundos_por_100, "Un ritmo")
        )

    @classmethod
    def desde(cls, tiempo: Tiempo, distancia: int) -> Ritmo:
        """Ritmo medio de nadar `distancia` en `tiempo`.

        Es el `/100` aritmético. La corrección de fatiga del sprint (un 50 no se
        sostiene al doble de distancia) es otra cosa y vive en el motor.
        """
        if not isinstance(tiempo, Tiempo):
            raise ValueError("Un ritmo se deriva de un Tiempo, no de un número suelto")
        if distancia <= 0:
            raise ValueError(f"La distancia tiene que ser positiva: {distancia}")
        return cls(tiempo.segundos / (distancia / 100.0))

    @classmethod
    def desde_texto(cls, texto: str) -> Ritmo:
        return cls(_parsear(texto))

    def a_tiempo(self, distancia: int) -> Tiempo:
        """Lo que se tarda en `distancia` metros sosteniendo este ritmo."""
        if distancia <= 0:
            raise ValueError(f"La distancia tiene que ser positiva: {distancia}")
        return Tiempo(self.segundos_por_100 * (distancia / 100.0))

    def texto(self, decimales: int = 2) -> str:
        return _formatear(self.segundos_por_100, decimales)

    def __sub__(self, otro: Ritmo) -> Mejora:
        if not isinstance(otro, Ritmo):
            return NotImplemented
        return Mejora(self.segundos_por_100 - otro.segundos_por_100, self.segundos_por_100)

    def __str__(self) -> str:
        return self.texto()


@dataclass(frozen=True, slots=True)
class Mejora:
    """Cuánto se bajó, en segundos **y** en fracción, sobre una base.

    `segundos > 0` es mejora (se bajó el tiempo); `segundos < 0` es regresión.
    `base` son los segundos de partida: es lo que permite dar el porcentaje sin
    que nadie lo recalcule por su cuenta.
    """

    segundos: float
    base: float

    def __post_init__(self) -> None:
        base = _positivo_finito(self.base, "La base de una mejora")
        if isinstance(self.segundos, bool) or not isinstance(self.segundos, (int, float)):
            raise ValueError("Los segundos de una mejora tienen que ser un número")
        segundos = float(self.segundos)
        if not math.isfinite(segundos):
            raise ValueError(f"Los segundos de una mejora tienen que ser finitos: {segundos!r}")
        if segundos >= base:
            raise ValueError(
                f"No se puede mejorar {segundos} s sobre una base de {base} s: "
                "el tiempo resultante sería cero o negativo"
            )
        object.__setattr__(self, "segundos", segundos)
        object.__setattr__(self, "base", base)

    @classmethod
    def entre(cls, inicial: Tiempo, final: Tiempo) -> Mejora:
        return inicial - final

    @classmethod
    def de_fraccion(cls, base: Tiempo | Ritmo | float, fraccion: float) -> Mejora:
        """La forma en que la expresa el motor científico: proporción decimal."""
        if isinstance(base, Tiempo):
            partida = base.segundos
        elif isinstance(base, Ritmo):
            partida = base.segundos_por_100
        else:
            partida = base
        return cls(partida * fraccion, partida)

    @property
    def fraccion(self) -> float:
        """Proporción decimal (0.025). El lenguaje de `ScienceEngine`."""
        return self.segundos / self.base

    @property
    def porcentaje(self) -> float:
        """Porcentaje (2.5). El lenguaje de la interfaz."""
        return self.fraccion * 100.0

    def es_regresion(self) -> bool:
        return self.segundos < 0

    def tiempo_resultante(self) -> Tiempo:
        """El tiempo al que lleva esta mejora desde su base."""
        return Tiempo(self.base - self.segundos)

    def texto(self, decimales: int = 2) -> str:
        signo = "+" if self.segundos >= 0 else "−"
        return f"{signo}{abs(self.segundos):.{decimales}f} s ({abs(self.porcentaje):.2f} %)"

    def __str__(self) -> str:
        return self.texto()
