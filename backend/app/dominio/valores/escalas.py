"""Escalas del dominio: los vocabularios cerrados, cada uno con lo suyo dentro.

Diez enums que hoy son cadenas sueltas repartidas entre columnas `String(12)`,
`Literal[...]` de Pydantic y claves de diccionarios científicos. Dos cosas
cambian al convertirlos en tipos:

* **`Fase` cerró P3** (2026-09-22). Convivían tres vocabularios de fase: las
  cinco claves científicas de `F_FASE`, los cuatro tramos que veía el
  entrenador (`Base/Construcción/Pico/Descenso`) y los cuatro de
  `PlanPhase.type` (`base|build|peak|taper`), y la base guardaba la etiqueta
  humana, así que la ciencia no podía leer lo que la aplicación persistía. Hoy
  este enum es el único: las fases del macrociclo **son** estas cinco, la base
  guarda su clave y el nombre que el entrenador le pone es texto libre aparte.
  Lleva su `F_FASE` y su banda de volumen **dentro**.
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
        # Solo el `value`. Aceptar además el `name` abría doce grafías en español
        # (`principiante`, `mejorando`, `agresivo`…) que ningún productor emite:
        # un segundo vocabulario creado sin querer, justo en el módulo cuyo
        # propósito es que no haya dos. Lo que sí tiene dos grafías vivas —el
        # perfil— lo declara su propio `desde_texto`.
        crudo = str(valor).strip().lower()
        for miembro in cls:
            if miembro.value.lower() == crudo:
                return miembro
        validos = ", ".join(m.value for m in cls)
        raise ValueError(f"{cls.__name__} no reconocido: {valor!r}. Válidos: {validos}")


# §2.4 — umbrales de clasificación por CSS (s/100 m), tabla de crol. Se lee de
# arriba abajo: el primer umbral que el ritmo NO supera manda. Única declaración
# desde que C4 borró `app/domain/engine.classify_level`, que era la otra.
_UMBRALES_DE_NIVEL: tuple[tuple[float, str], ...] = (
    (150.0, "beginner"),
    (120.0, "recreational"),
    (95.0, "advanced"),
    (70.0, "competitive"),
)


class Nivel(_EscalaTextual):
    """Nivel del atleta. **Siempre derivado**: no se escribe a mano ni se guarda.

    `desde_umbral` recibe el ritmo de **umbral**: desde el paso 4 (2026-08-17)
    ese umbral es el **test aeróbico del atleta** cuando existe, y solo si no hay
    test se estima desde el ritmo de carrera. Era el defecto 1 de §10.4: la tabla
    está calibrada para un test de 400/1500 y se la alimentaba con el ritmo de un
    200, así que una décima cambiaba el volumen prescrito un 45 %. Quién elige
    una u otra fuente es `servicios.envolvente.nivel_de`; este tipo solo garantiza
    que la clasificación viva en un sitio.
    """

    PRINCIPIANTE = "beginner"
    RECREATIVO = "recreational"
    AVANZADO = "advanced"
    COMPETITIVO = "competitive"
    ELITE = "elite"

    @classmethod
    def desde_umbral(cls, umbral: Ritmo) -> Nivel:
        if not isinstance(umbral, Ritmo):
            raise TypeError("El nivel se deriva de un Ritmo de umbral, no de un número suelto")
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

    @classmethod
    def para_distancia(cls, distancia: int) -> Perfil:
        """El perfil que sugiere la prueba: velocidad 50-100 · medio fondo
        200-400 · fondo 800-1500. El entrenador puede cambiarlo.

        Está aquí y no en `Prueba` porque el motor necesita el perfil de una
        distancia suelta —para clasificar el nivel o calcular zonas— y exigirle
        una `Prueba` completa lo obligaría a inventarse un estilo. `Prueba`
        delega en esto, así que sigue habiendo una sola regla.
        """
        if distancia <= 100:
            return cls.VELOCIDAD
        if distancia <= 400:
            return cls.MEDIO_FONDO
        return cls.FONDO

    @classmethod
    def desde_texto(cls, valor: str) -> Perfil:
        """Traga **las dos** grafías, que es la razón de existir de este tipo.

        `profile_for_event()` devuelve «medio fondo» con espacio y es la clave de
        `ZONE_OVER_RACE`; la base de datos y el frontend escriben `medio_fondo`.
        Si la ida tiene `clave_cientifica` y la vuelta no la acepta, el texto que
        viene del lado científico no se puede convertir en `Perfil` — que es el
        `KeyError` de producción que el docstring dice evitar.
        """
        return super().desde_texto(str(valor).strip().replace(" ", "_"))

    @property
    def clave_cientifica(self) -> str:
        return self.value.replace("_", " ")


# §4.3 F_FASE · §9.1 banda de volumen. Única declaración desde C4.
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

# Es el nombre con el que nace cada fase de un macrociclo nuevo, así que va
# entero: abreviarlo para que quepa en una columna es cosa de quien la pinta.
_ETIQUETAS_DE_FASE: dict[str, str] = {
    "base_general": "Base general",
    "base_especifica": "Base específica",
    "umbral_css": "Umbral CSS",
    "pre_competitivo": "Pre-competitivo",
    "taper": "Taper",
    "extension": "Extensión",
}


class Fase(_EscalaTextual):
    """Fase del macrociclo, con su multiplicador de mejora y su banda de volumen.

    **Las fases de un macrociclo son estas cinco** (P3, cerrado el 2026-09-22).
    Los cuatro tramos que la interfaz enseñaba antes (`Base/Construcción/Pico/
    Descenso`, guardados como `base|build|peak|taper`) no eran una versión
    gruesa de estas: eran otro vocabulario, y ninguna regla decía cómo se
    repartían cuatro sobre cinco. Se resolvió quitando el de cuatro, no
    traduciéndolo: la migración `a3f1c2d4e5b6` convirtió una sola vez las filas
    que había, y desde entonces la base solo conoce estas claves.

    Por eso `desde_texto` acepta **solo** las seis claves y rechaza
    `"Construcción"` o `"build"`: una traducción viva sería la segunda copia de
    la regla que este tipo existe para tener una sola vez.
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

    @classmethod
    def secuencia(cls) -> tuple[Fase, ...]:
        """Las **cinco** fases del macrociclo, en orden cronológico.

        `EXTENSION` queda fuera a propósito: no es una fase del macro sino lo que
        viene después cuando la meta supera el techo.

        Existe por la misma razón que `Zona.ordenadas()`: este orden ya vive en
        `MACRO_15_FASES` del motor, y sin exponerlo aquí el primero que reparta
        fases sobre semanas escribirá una `FASE_ORDER` suelta al lado.
        """
        return (
            cls.BASE_GENERAL, cls.BASE_ESPECIFICA, cls.UMBRAL_CSS,
            cls.PRE_COMPETITIVO, cls.TAPER,
        )

    @classmethod
    def del_macro(cls, valor: str) -> Fase:
        """La fase de un tramo del macrociclo: cualquiera menos la extensión.

        La extensión no es un tramo que el entrenador pueda poner en su plan:
        es lo que el motor enseña **después** del macro cuando la meta supera el
        techo. Una fase del macro marcada como extensión no tiene `f_fase` que
        signifique nada dentro de las semanas del plan.
        """
        fase = cls.desde_texto(valor)
        if fase.es_extension:
            raise ValueError(
                "La extensión no es una fase del macrociclo: es lo que viene después "
                "cuando la meta supera el techo. Elige una de "
                + ", ".join(f.value for f in cls.secuencia())
            )
        return fase

    @property
    def orden(self) -> int:
        """Posición cronológica, 0 = la primera. La extensión va detrás de todas."""
        secuencia = type(self).secuencia()
        return secuencia.index(self) if self in secuencia else len(secuencia)

    def banda_de_volumen(self, nivel: Nivel) -> tuple[float, float]:
        """Km semanales {min, max} para este nivel en esta fase.

        Es un **aviso**, nunca un valor por defecto ni un límite: el total lo pone
        el entrenador y la ciencia pone la forma (decisión R6, REDISENO §10.1).
        """
        if not isinstance(nivel, Nivel):
            raise TypeError("La banda de volumen se pide con un Nivel")
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

    @property
    def mide_el_umbral(self) -> bool:
        """Si su ritmo es un CSS: el CSS de Wakayoshi, el T30 (Olbrecht) o uno
        ya calculado. Un T15 o uno libre se nadan más cortos y por encima del
        umbral; la carga (`servicios.banister`) solo los usa a falta de otro."""
        return self in (TipoDeTest.CSS, TipoDeTest.T30, TipoDeTest.DIRECT)


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


# `Veredicto` (la factibilidad de una meta) vive en `veredicto.py` desde C9: dejó
# de ser tres claves sueltas y lleva los umbrales que deciden entre ellas.
