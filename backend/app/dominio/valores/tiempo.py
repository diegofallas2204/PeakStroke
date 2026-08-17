"""Tiempo, duración, ritmo y mejora — las cantidades del rendimiento, con su unidad.

Hoy ocho columnas `float` mezclan dos unidades: `current_time`, `goal_time`,
`expected_time`, `recalc_time` y `real_time` son segundos absolutos; `avg_per100`,
`css_ms` y `pace_100m` son segundos por 100 m. Nada impide restar un ritmo de un
tiempo y obtener un número que parece correcto (REDISENO §3.1, hallazgo P6).

`Tiempo` y `Ritmo` son tipos **distintos** a propósito: no comparten operadores,
así que esa resta deja de escribirse. La conversión entre ellos existe, pero hay
que pedirla y hay que decir con qué distancia — que es exactamente el dato que
falta cuando alguien los mezcla.

`Duracion` existe porque `Tiempo` hacía de dos cosas y **solo una es siempre
positiva**: un nado, y un instante o un hueco del reloj. La salida de la primera
repetición de una serie **es 0**, y el descanso que se perdió en un parcial es
**negativo** — literalmente `missed_intervals`. Con un solo tipo, ni
`Parcial.inicio` se podía construir ni se podía escribir la conversión
reloj→nadado, que es la invariante que más protege la base aeróbica. La señal de
que faltaba estaba dentro de esta misma librería: `zona.py` se salía del tipo
—`Tiempo(a.segundos + b.segundos)`— para hacer aritmética elemental.

    Tiempo      un tiempo NADADO, o un intervalo de salida. Siempre > 0.
    Duracion    segundos con signo: instantes, huecos, descansos. Admite 0 y < 0.

`Mejora` existe porque los dos motores actuales expresan lo mismo de dos formas:
`engine/progression.py` maneja segundos y `ScienceEngine` maneja fracciones
decimales. Un tipo que lleva las dos elimina la conversión repetida a mano. Su
`base` está **tipada** (`Tiempo | Ritmo`) y no es un `float`: cuando era un float,
una mejora de ritmo salía convertida en un tiempo absoluto —P6 reentrando por el
único tipo que une las dos unidades—, porque una base que no sabe de qué era solo
puede adivinar.

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


def _finito(valor: float, que: str) -> float:
    """Número real, con el signo que sea. La guarda de `Duracion`."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise TypeError(f"{que} tiene que ser un número, no {type(valor).__name__}")
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{que} tiene que ser finito, no {valor!r}")
    return numero


def _segundos_de(base: Tiempo | Ritmo) -> float:
    """Los segundos de una base, sea la unidad que sea."""
    return base.segundos if isinstance(base, Tiempo) else base.segundos_por_100


def _al_reloj(segundos: float, paso: float) -> float:
    """Múltiplo de `paso` inmediatamente por encima. Ver `Tiempo.al_reloj`."""
    if paso <= 0:
        raise ValueError("El paso del reloj tiene que ser positivo")
    return math.ceil(segundos / paso - 1e-9) * paso


def _positivo_finito(valor: float, que: str) -> float:
    # TypeError cuando lo que llega no es de la clase correcta, ValueError cuando
    # sí lo es pero el valor no vale. La distinción no es de estilo: estos objetos
    # se construyen dentro de validadores de Pydantic, que convierte **cualquier**
    # ValueError en un 422. Un bug de programación tiene que romper con un 500 que
    # se vea en el log, no aparecerle al entrenador como «su formulario está mal».
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise TypeError(f"{que} tiene que ser un número, no {type(valor).__name__}")
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{que} tiene que ser finito, no {valor!r}")
    if numero <= 0:
        raise ValueError(f"{que} tiene que ser positivo: {numero}")
    return numero


@dataclass(frozen=True, slots=True, order=True)
class Duracion:
    """Segundos **con signo**: instantes del reloj, huecos, descansos.

    Es el tipo de todo lo que no es un nado. Admite 0 —la salida de la primera
    repetición de una serie es exactamente 0— y admite negativos: cuando un
    nadador llega después de su salida, el descanso que le quedaba es negativo, y
    eso no es un error de dato sino el hecho que hay que registrar.

    No se mezcla con `Ritmo` (no comparten operadores) ni se convierte sola en
    `Tiempo`: para eso está `a_tiempo()`, que falla si no es positiva.
    """

    segundos: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "segundos", _finito(self.segundos, "Una duración"))

    @classmethod
    def desde_texto(cls, texto: str) -> Duracion:
        crudo = str(texto).strip()
        signo = -1.0 if crudo.startswith("-") else 1.0
        return cls(signo * _parsear(crudo.lstrip("+-")))

    def texto(self, decimales: int = 2) -> str:
        signo = "-" if self.segundos < 0 else ""
        return f"{signo}{_formatear(abs(self.segundos), decimales)}"

    def a_tiempo(self) -> Tiempo:
        """Convierte a `Tiempo`. Explícito a propósito: falla si no es positiva."""
        return Tiempo(self.segundos)

    def al_reloj(self, paso: float = PASO_DE_RELOJ_S) -> Duracion:
        return Duracion(_al_reloj(self.segundos, paso))

    def es_negativa(self) -> bool:
        return self.segundos < 0

    def __add__(self, otra: Duracion) -> Duracion:
        if not isinstance(otra, Duracion):
            return NotImplemented
        return Duracion(self.segundos + otra.segundos)

    def __sub__(self, otra: Duracion) -> Duracion:
        if not isinstance(otra, Duracion):
            return NotImplemented
        return Duracion(self.segundos - otra.segundos)

    def __neg__(self) -> Duracion:
        return Duracion(-self.segundos)

    def __abs__(self) -> Duracion:
        return Duracion(abs(self.segundos))

    def __str__(self) -> str:
        return self.texto()


@dataclass(frozen=True, slots=True, order=True)
class Tiempo:
    """Segundos absolutos: lo que tarda alguien en nadar una distancia.

    Siempre positivo. Lo que puede valer 0 o ser negativo es una `Duracion`.
    """

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
        return Tiempo(_al_reloj(self.segundos, paso))

    def a_duracion(self) -> Duracion:
        """El mismo número visto como cantidad con signo, para poder operarlo."""
        return Duracion(self.segundos)

    def diferencia(self, otro: Tiempo) -> Duracion:
        """Aritmética de reloj: cuánto hay de `otro` a `self`, con signo.

        Distinto de `-`, que es la lectura de **rendimiento** y devuelve `Mejora`.
        Restar dos llegadas del reloj no es una mejora del 66 %, es un hueco de
        60 segundos — y es lo que convierte llegadas acumuladas en tiempos
        nadados.
        """
        if not isinstance(otro, Tiempo):
            raise TypeError("La diferencia de reloj se toma entre dos Tiempo")
        return Duracion(self.segundos - otro.segundos)

    def __add__(self, duracion: Duracion) -> Tiempo:
        """Desplazar un tiempo por una duración sigue siendo un tiempo."""
        if not isinstance(duracion, Duracion):
            return NotImplemented
        return Tiempo(self.segundos + duracion.segundos)

    def __sub__(self, otro: Tiempo) -> Mejora:
        """`inicial - final` → la `Mejora` que va de uno a otro.

        Positiva cuando el segundo es más rápido, que es como se lee en natación:
        bajar el tiempo es mejorar. La base es `self`, el tiempo de partida.

        Para la aritmética de reloj —restar dos instantes— está `diferencia()`.
        """
        if not isinstance(otro, Tiempo):
            return NotImplemented
        return Mejora(self.segundos - otro.segundos, self)

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
            raise TypeError("Un ritmo se deriva de un Tiempo, no de un número suelto")
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
        return Mejora(self.segundos_por_100 - otro.segundos_por_100, self)

    def __str__(self) -> str:
        return self.texto()


@dataclass(frozen=True, slots=True)
class Mejora:
    """Cuánto se bajó, en segundos **y** en fracción, sobre una base **tipada**.

    `segundos > 0` es mejora (se bajó el tiempo); `segundos < 0` es regresión.

    `base` es el `Tiempo` o el `Ritmo` de partida, no un `float`. Cuando era un
    float, el tipo perdía la unidad y `Ritmo(80) - Ritmo(78)` daba un resultado
    de tipo `Tiempo`: una mejora de ritmo salía convertida en un tiempo absoluto
    de 1:18. Es P6 —la mezcla de las dos unidades— reentrando por el único tipo
    que las une, y pasaba porque una base que no sabe de qué era solo puede
    adivinar. Con la base tipada, `resultado` devuelve **el mismo tipo**.
    """

    segundos: float
    base: Tiempo | Ritmo

    def __post_init__(self) -> None:
        if not isinstance(self.base, (Tiempo, Ritmo)):
            raise TypeError(
                "La base de una mejora es el Tiempo o el Ritmo de partida, "
                f"no {type(self.base).__name__}: sin unidad no se puede decir de qué mejoró"
            )
        segundos = _finito(self.segundos, "Los segundos de una mejora")
        partida = _segundos_de(self.base)
        if segundos >= partida:
            raise ValueError(
                f"No se puede mejorar {segundos} s sobre una base de {partida} s: "
                "el resultado sería cero o negativo"
            )
        object.__setattr__(self, "segundos", segundos)

    @classmethod
    def entre(cls, inicial: Tiempo, final: Tiempo) -> Mejora:
        return inicial - final

    @classmethod
    def de_fraccion(cls, base: Tiempo | Ritmo, fraccion: float) -> Mejora:
        """La forma en que la expresa el motor científico: proporción decimal."""
        return cls(_segundos_de(base) * fraccion, base)

    @property
    def base_segundos(self) -> float:
        """La partida en segundos, para cuando hace falta el número pelado."""
        return _segundos_de(self.base)

    @property
    def fraccion(self) -> float:
        """Proporción decimal (0.025). El lenguaje de `ScienceEngine`."""
        return self.segundos / self.base_segundos

    @property
    def porcentaje(self) -> float:
        """Porcentaje (2.5). El lenguaje de la interfaz."""
        return self.fraccion * 100.0

    def es_regresion(self) -> bool:
        return self.segundos < 0

    @property
    def resultado(self) -> Tiempo | Ritmo:
        """A dónde lleva esta mejora, **en el mismo tipo que la base**.

        Mejorar un ritmo da un ritmo; mejorar un tiempo da un tiempo. Que esto
        sea así por construcción es el punto entero de tipar `base`.
        """
        restante = self.base_segundos - self.segundos
        return Tiempo(restante) if isinstance(self.base, Tiempo) else Ritmo(restante)

    def texto(self, decimales: int = 2) -> str:
        signo = "+" if self.segundos >= 0 else "−"
        return f"{signo}{abs(self.segundos):.{decimales}f} s ({abs(self.porcentaje):.2f} %)"

    def __str__(self) -> str:
        return self.texto()
