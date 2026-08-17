"""La prueba: `(distancia, estilo)` como un solo objeto que se niega a ser inválido.

Hasta el 2026-08-16 la validez de una prueba fue una **función suelta**
(`engine/events.allowed_strokes`) que cada formulario y cada endpoint tenía que
acordarse de llamar. Por eso pudo existir durante meses una segunda copia en
`domain/engine.py` que daba el 50 combinado por válido: una prueba que no existe
en natación. Borrar la copia mala (A1, 2026-08-13) tapaba el síntoma; mientras la
regla fuera una función, la siguiente copia volvía a entrar (REDISENO §0, P6 → P2).

Aquí la validez es una **invariante del constructor**: `Prueba(50, COMBINADO)`
levanta `ValueError` y no hay ninguna forma de tener una en las manos. Los tres
validadores que llamaban a `is_valid_event` construyen una `Prueba` y ya está;
`app/engine/events.py` se borró en esa misma migración.

Queda una copia fuera de este proceso: `frontend/src/lib/constants.ts`, que filtra
los combos en la interfaz. El rediseño es del backend, así que sigue viva y tiene
que decir lo mismo — el backend es el que manda, y aquí es donde se rechaza.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Self

from .escalas import Perfil

# ── Estilo ───────────────────────────────────────────────────────────────────

# Alias aceptados → clave canónica en español. Une los dos diccionarios que hoy
# existen: `engine/events._STROKE_ALIASES` (a español) y `domain.STROKE_ALIASES`
# (a inglés). Aquí el alias entra y sale un `Estilo`; las dos grafías son
# propiedades del miembro, no dos tablas que puedan separarse.
_ALIAS_DE_ESTILO: dict[str, str] = {
    "libre": "libre", "crol": "libre", "freestyle": "libre",
    "espalda": "espalda", "dorso": "espalda", "backstroke": "espalda",
    "pecho": "pecho", "braza": "pecho", "breaststroke": "pecho",
    "mariposa": "mariposa", "butterfly": "mariposa",
    "combinado": "combinado", "im": "combinado", "individual_medley": "combinado",
}

# Clave con la que las tablas científicas indexan cada estilo, y corrección de
# T-pace en s/100 m sobre crol (§7.1, CALIBRADO con el pool nacional 2026-06-13).
# El combinado es la media de los cuatro: así se nada un IM, 25 % de cada uno.
_DATOS_DE_ESTILO: dict[str, tuple[str, float]] = {
    "libre": ("freestyle", 0.0),
    "espalda": ("backstroke", 15.0),
    "pecho": ("breaststroke", 23.0),
    "mariposa": ("butterfly", 10.0),
    "combinado": ("individual_medley", (0.0 + 15.0 + 23.0 + 10.0) / 4),
}


class Estilo(Enum):
    LIBRE = "libre"
    ESPALDA = "espalda"
    PECHO = "pecho"
    MARIPOSA = "mariposa"
    COMBINADO = "combinado"

    @classmethod
    def desde_texto(cls, valor: str) -> Self:
        clave = _ALIAS_DE_ESTILO.get(str(valor).strip().lower())
        if clave is None:
            validos = ", ".join(m.value for m in cls)
            raise ValueError(f"Estilo no reconocido: {valor!r}. Válidos: {validos}")
        return cls(clave)

    @property
    def clave_cientifica(self) -> str:
        """Cómo lo indexan las tablas del motor (`freestyle`, `individual_medley`…)."""
        return _DATOS_DE_ESTILO[self.value][0]

    @property
    def correccion_tpace_s(self) -> float:
        """Segundos por 100 m que este estilo suma sobre el crol."""
        return _DATOS_DE_ESTILO[self.value][1]

    @property
    def etiqueta(self) -> str:
        return self.value.capitalize()


# ── Piscina ──────────────────────────────────────────────────────────────────

# Corrección por piscina de 25 m: el viraje extra cada 25 m baja el parcial.
# Factores VALIDADOS con el pool (ratio real SCM/LCM por especialidad, 2026-06-13).
_FACTOR_DE_25: dict[Perfil, float] = {
    Perfil.VELOCIDAD: 0.982,
    Perfil.MEDIO_FONDO: 0.979,
    Perfil.FONDO: 0.968,
}
_FACTOR_DE_25_POR_DEFECTO = 0.978


class Piscina(Enum):
    LARGA = "50"
    CORTA = "25"

    @classmethod
    def desde_texto(cls, valor: str) -> Self:
        crudo = str(valor).strip().lower()
        for miembro in cls:
            if crudo in (miembro.value, miembro.name.lower(), f"{miembro.value}m"):
                return miembro
        raise ValueError(f"Piscina no reconocida: {valor!r}. Válidas: 50, 25")

    @property
    def metros(self) -> int:
        return int(self.value)

    def factor(self, perfil: Perfil) -> float:
        """Factor sobre el ritmo. 1.0 en piscina de 50 m, por definición."""
        if self is Piscina.LARGA:
            return 1.0
        return _FACTOR_DE_25.get(perfil, _FACTOR_DE_25_POR_DEFECTO)


# ── Prueba ───────────────────────────────────────────────────────────────────

_TODOS = frozenset(Estilo)
_SIN_COMBINADO = frozenset(e for e in Estilo if e is not Estilo.COMBINADO)

# Distancias con entrada propia en las tablas científicas (I_max, tier, mezcla de
# zonas). Una prueba de 300 se indexa por la más cercana de estas.
EVENTOS_DE_REFERENCIA: tuple[int, ...] = (50, 100, 200, 400, 800, 1500)

# La distancia a partir de la cual una prueba es Tier 1 (regla aeróbica).
DISTANCIA_TIER_1 = 400


@dataclass(frozen=True, slots=True)
class Prueba:
    """Una prueba de natación válida. Las inválidas no se pueden construir.

    | Distancia  | Estilos válidos                                    |
    |------------|----------------------------------------------------|
    | ≥ 600 m    | solo libre                                         |
    | 300–599 m  | libre, combinado                                   |
    | 100–299 m  | los cinco                                          |
    | < 100 m    | libre, espalda, pecho, mariposa (**no** combinado) |
    """

    distancia: int
    estilo: Estilo = Estilo.LIBRE

    def __post_init__(self) -> None:
        # Se acepta el estilo como texto porque es como llega de un formulario o
        # de una fila: normalizarlo aquí es lo que hace que el error salga en la
        # construcción y no tres capas más abajo.
        if not isinstance(self.estilo, Estilo):
            object.__setattr__(self, "estilo", Estilo.desde_texto(self.estilo))
        # TypeError y no ValueError: esta clase se construye dentro de validadores
        # de Pydantic, que convierte cualquier ValueError en un 422. Que la
        # distancia no sea entera es un bug de programación —Pydantic ya la
        # garantiza `int`— y tiene que romper con un 500 visible, no aparecerle al
        # entrenador como un error de su formulario. El estilo desconocido y la
        # prueba imposible sí son ValueError: esos sí los escribe una persona.
        if isinstance(self.distancia, bool) or not isinstance(self.distancia, int):
            raise TypeError(f"La distancia son metros enteros: {self.distancia!r}")
        if self.distancia <= 0:
            raise ValueError(f"La distancia tiene que ser positiva: {self.distancia}")
        validos = self.estilos_validos(self.distancia)
        if self.estilo not in validos:
            legibles = ", ".join(sorted(e.value for e in validos))
            raise ValueError(
                f"No existe la prueba {self.distancia} {self.estilo.value}. "
                f"En {self.distancia} m solo se nada: {legibles}"
            )

    @staticmethod
    def estilos_validos(distancia: int) -> frozenset[Estilo]:
        """Regla del deporte. Fuente única, antes en `engine.events.allowed_strokes`."""
        if distancia >= 600:
            return frozenset({Estilo.LIBRE})
        if distancia >= 300:
            return frozenset({Estilo.LIBRE, Estilo.COMBINADO})
        if distancia >= 100:
            return _TODOS
        return _SIN_COMBINADO

    @classmethod
    def es_valida(cls, distancia: int, estilo: Estilo | str) -> bool:
        """Para filtrar combos en la interfaz sin capturar excepciones."""
        try:
            cls(distancia, estilo)
        except ValueError:
            return False
        return True

    def perfil_sugerido(self) -> Perfil:
        """velocidad 50-100 · medio fondo 200-400 · fondo 800-1500."""
        if self.distancia <= 100:
            return Perfil.VELOCIDAD
        if self.distancia <= 400:
            return Perfil.MEDIO_FONDO
        return Perfil.FONDO

    def tier(self) -> int:
        """1 = regla aeróbica (≥ 400 m) · 2 = ventanas de velocidad (< 400 m)."""
        return 1 if self.distancia >= DISTANCIA_TIER_1 else 2

    def es_aerobica(self) -> bool:
        return self.tier() == 1

    def evento_mas_cercano(self) -> int:
        """Distancia de referencia con la que indexar las tablas científicas."""
        return min(EVENTOS_DE_REFERENCIA, key=lambda d: abs(d - self.distancia))

    def texto(self) -> str:
        return f"{self.distancia} {self.estilo.value}"

    def __str__(self) -> str:
        return self.texto()
