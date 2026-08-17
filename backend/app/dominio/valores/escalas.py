"""Escalas del dominio: los vocabularios cerrados, cada uno con lo suyo dentro.

Diez enums que hoy son cadenas sueltas repartidas entre columnas `String(12)`,
`Literal[...]` de Pydantic y claves de diccionarios científicos. Dos cosas
cambian al convertirlos en tipos:

* **`Fase` cierra P3.** Hoy hay tres vocabularios de fase vivos a la vez: las
  cinco claves científicas de `F_FASE`, las cuatro etiquetas de `DEFAULT_PHASES`
  (`Base/Construcción/Pico/Descenso`) y las cuatro de `PlanPhase.type`
  (`base|build|peak|taper`). La base de datos guarda la etiqueta humana, así que
  la ciencia no puede leer lo que la aplicación persiste. Este enum es la única
  fuente, y lleva su `F_FASE` y su banda de volumen **dentro**.
* **`Nivel` se deriva siempre**, nunca se escribe a mano ni se guarda.

El `value` de cada miembro es la clave que ya usan las tablas científicas o la
base de datos (`"beginner"`, `"active"`, `"improving"`…): así el tipo entra en el
código existente sin traducir nada, y `tests/test_valores_vs_motor.py` fija que
no se separen de su fuente.
"""
from __future__ import annotations

from enum import Enum
from typing import Self

from .tiempo import Ritmo


class _EscalaTextual(Enum):
    """Base común: construir desde el texto que llega de la base o del formulario."""

    @classmethod
    def desde_texto(cls, valor: str) -> Self:
        crudo = str(valor).strip().lower()
        for miembro in cls:
            if miembro.value.lower() == crudo or miembro.name.lower() == crudo:
                return miembro
        validos = ", ".join(m.value for m in cls)
        raise ValueError(f"{cls.__name__} no reconocido: {valor!r}. Válidos: {validos}")


# §2.4 — umbrales de clasificación por CSS (s/100 m), tabla de crol.
# Fuente: `app.domain.engine.classify_level`. Se lee de arriba abajo: el primer
# umbral que el ritmo NO supera manda.
_UMBRALES_DE_NIVEL: tuple[tuple[float, str], ...] = (
    (150.0, "beginner"),
    (120.0, "recreational"),
    (95.0, "advanced"),
    (70.0, "competitive"),
)


class Nivel(_EscalaTextual):
    """Nivel del atleta. **Siempre derivado**: no se escribe a mano ni se guarda.

    `desde_umbral` recibe el ritmo de **umbral** (un CSS medido, o el ritmo de
    carrera corregido por el factor MVO2 mientras no haya test). Quién calcula
    ese umbral es una decisión del paso 4 del rediseño: hoy `envelope.level_for`
    lo deriva del ritmo de un 200 con una tabla calibrada para un test de
    400/1500, y por eso una décima de segundo cambia el volumen prescrito un 45 %
    (REDISENO §10.4, defecto 1). Este tipo no arregla eso; solo garantiza que la
    clasificación viva en un sitio.
    """

    PRINCIPIANTE = "beginner"
    RECREATIVO = "recreational"
    AVANZADO = "advanced"
    COMPETITIVO = "competitive"
    ELITE = "elite"

    @classmethod
    def desde_umbral(cls, umbral: Ritmo) -> Nivel:
        if not isinstance(umbral, Ritmo):
            raise ValueError("El nivel se deriva de un Ritmo de umbral, no de un número suelto")
        for tope, clave in _UMBRALES_DE_NIVEL:
            if umbral.segundos_por_100 > tope:
                return cls(clave)
        return cls.ELITE


class Perfil(_EscalaTextual):
    """Perfil de entrenamiento, sugerido por la prueba; el coach puede cambiarlo.

    `clave_cientifica` existe porque las tablas del motor indexan «medio fondo»
    con espacio mientras la base de datos y el frontend escriben `medio_fondo`.
    Dos grafías de lo mismo es exactamente la clase de detalle que un tipo se
    traga para que no vuelva a aparecer un `KeyError` de producción.
    """

    VELOCIDAD = "velocidad"
    MEDIO_FONDO = "medio_fondo"
    FONDO = "fondo"

    @property
    def clave_cientifica(self) -> str:
        return self.value.replace("_", " ")


# §4.3 F_FASE · §9.1 banda de volumen. Fuente: `app.domain.engine`.
# (multiplicador de mejora, clave de la banda de volumen que le toca)
_DATOS_DE_FASE: dict[str, tuple[float, str]] = {
    "base_general": (0.60, "base_general"),
    "base_especifica": (0.80, "base_especifica"),
    "umbral_css": (1.00, "umbral_css"),
    "pre_competitivo": (1.05, "umbral_css"),   # no tiene banda propia
    "taper": (1.15, "taper"),
    "extension": (1.00, "umbral_css"),         # las extra mantienen volumen de umbral
}

# §9.1 — volumen semanal (km) por nivel y banda de fase {min, max}.
_VOLUMEN_SEMANAL_KM: dict[Nivel, dict[str, tuple[float, float]]] = {
    Nivel.PRINCIPIANTE: {"base_general": (10, 20), "base_especifica": (15, 28),
                         "umbral_css": (15, 25), "taper": (5, 12)},
    Nivel.RECREATIVO:   {"base_general": (18, 32), "base_especifica": (25, 40),
                         "umbral_css": (22, 38), "taper": (8, 18)},
    Nivel.AVANZADO:     {"base_general": (25, 45), "base_especifica": (35, 55),
                         "umbral_css": (30, 50), "taper": (12, 25)},
    Nivel.COMPETITIVO:  {"base_general": (35, 55), "base_especifica": (45, 65),
                         "umbral_css": (40, 60), "taper": (15, 30)},
    Nivel.ELITE:        {"base_general": (50, 80), "base_especifica": (60, 90),
                         "umbral_css": (55, 85), "taper": (20, 40)},
}

_ETIQUETAS_DE_FASE: dict[str, str] = {
    "base_general": "Base general",
    "base_especifica": "Base especif.",
    "umbral_css": "Umbral CSS",
    "pre_competitivo": "Pre-comp.",
    "taper": "Taper",
    "extension": "Extensión",
}


class Fase(_EscalaTextual):
    """Fase del macrociclo, con su multiplicador de mejora y su banda de volumen.

    `desde_texto` acepta **solo** estas seis claves. No traduce
    `Base/Construcción/Pico/Descenso` ni `base|build|peak|taper`: son cuatro
    tramos contra cinco fases y el reparto no está decidido —lo decide la fusión
    de motores (paso 4)—. Adivinarlo aquí sería inventar la sexta versión de la
    regla que este tipo existe para cerrar.
    """

    BASE_GENERAL = "base_general"
    BASE_ESPECIFICA = "base_especifica"
    UMBRAL_CSS = "umbral_css"
    PRE_COMPETITIVO = "pre_competitivo"
    TAPER = "taper"
    EXTENSION = "extension"

    @property
    def f_fase(self) -> float:
        """Multiplicador de mejora de la fase (§4.3)."""
        return _DATOS_DE_FASE[self.value][0]

    @property
    def clave_de_volumen(self) -> str:
        """Banda de volumen que le toca (pre-competitivo y extensión no tienen propia)."""
        return _DATOS_DE_FASE[self.value][1]

    @property
    def etiqueta(self) -> str:
        return _ETIQUETAS_DE_FASE[self.value]

    @property
    def es_extension(self) -> bool:
        return self is Fase.EXTENSION

    def banda_de_volumen(self, nivel: Nivel) -> tuple[float, float]:
        """Km semanales {min, max} para este nivel en esta fase.

        Es un **aviso**, nunca un valor por defecto ni un límite: el total lo pone
        el entrenador y la ciencia pone la forma (decisión R6, REDISENO §10.1).
        """
        if not isinstance(nivel, Nivel):
            raise ValueError("La banda de volumen se pide con un Nivel")
        return _VOLUMEN_SEMANAL_KM[nivel][self.clave_de_volumen]


class Especialidad(_EscalaTextual):
    """Especialidad del atleta — de la persona, no de la prueba que nade hoy."""

    VELOCIDAD = "velocidad"
    MEDIO_FONDO = "medio_fondo"
    FONDO = "fondo"
    AGUAS_ABIERTAS = "aguas_abiertas"

    @property
    def etiqueta(self) -> str:
        return self.value.replace("_", " ").capitalize()


class Genero(_EscalaTextual):
    F = "F"
    M = "M"


class TipoDeTest(_EscalaTextual):
    """Tipo de test aeróbico.

    `distancia_rep_fija` es la regla que hoy vive suelta en
    `aerobic_tests/service.py` (`100 if test_type in ("T30", "T15")`): un T30 son
    repeticiones de 100 por definición, y aceptar otra distancia produce una base
    aeróbica que no es comparable con ningún otro T30.
    """

    T30 = "T30"
    T15 = "T15"
    CUSTOM = "CUSTOM"
    CSS = "CSS"
    DIRECT = "DIRECT"

    @property
    def distancia_rep_fija(self) -> int | None:
        return 100 if self in (TipoDeTest.T30, TipoDeTest.T15) else None

    @property
    def tiene_parciales(self) -> bool:
        return self in (TipoDeTest.T30, TipoDeTest.T15, TipoDeTest.CUSTOM)


class ModoDeIngreso(_EscalaTextual):
    """Cómo apuntó el entrenador los números de un test.

    `REP` = tiempo nadado de cada repetición. `CLOCK` = llegada acumulada del
    reloj de pared. En la base de datos se guarda **siempre** el tiempo nadado:
    el modo describe la entrada, no el almacenamiento.
    """

    REP = "rep"
    CLOCK = "clock"

    @property
    def es_acumulado(self) -> bool:
        return self is ModoDeIngreso.CLOCK


class Tendencia(_EscalaTextual):
    """Deriva de la pendiente de los parciales del test, no se elige."""

    MEJORANDO = "improving"
    ESTABLE = "stable"
    EMPEORANDO = "declining"


class EstadoDeMacro(_EscalaTextual):
    ACTIVO = "active"
    BORRADOR = "draft"
    TERMINADO = "finished"
    SUSPENDIDO = "suspended"


class Veredicto(_EscalaTextual):
    """Factibilidad de una meta: qué dice el motor de lo que pide el entrenador."""

    OK = "ok"
    AVISO = "warning"
    AGRESIVO = "aggressive"
