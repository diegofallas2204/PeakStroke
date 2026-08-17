"""Zonas, prescripciones y el juego completo de una prueba.

Una prescripción de natación son **dos** números, no uno:

    10 × 100  a 1:18  salida 1:30
                ^^^^         ^^^^
                ritmo        intervalo de salida

`Prescripcion` los lleva juntos y comprueba que cuadran, porque separarlos es lo
que hacía que la mitad se olvidara en algún consumidor.

`Zona` es un enum **ordenado**. La jerarquía R1 → R2 → MVO2 → RL → V (de lento a
rápido) vive hoy en una lista suelta, `ZONE_ORDER` en `engine/send_off.py`, que
`engine/zones.py` reexporta con un comentario avisando de que si las dos se
separan, una zona nueva se convierte en un 500 en la tabla del equipo. Con un
enum ordenado no hay dos listas que separar: el orden **es** el tipo.

Comparar zonas compara **intensidad**: `Zona.R1 < Zona.V`. `Zona.ordenadas()` da
la tupla en el orden de siempre, que es el mismo.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Self

from .escalas import Perfil
from .prueba import Piscina, Prueba
from .tiempo import PASO_DE_RELOJ_S, Duracion, Ritmo, Tiempo

# Etiqueta · descanso como fracción del trabajo · (suelo, techo) del descanso en s.
#
# Los ratios siguen la progresión fisiológica de la nota 03 del vault y las
# prescripciones de Maglischo (*Swimming Fastest*, 2003). El principio que ordena
# la tabla: recortar el descanso de una zona rápida no la hace más dura, la
# cambia de zona — por eso el descanso crece con la intensidad y nunca al revés.
# Los topes existen porque el ratio solo, en los extremos, produce disparates: un
# 25 de velocidad pediría 26 s (insuficiente para recuperar la PCr) y un 800 de
# base aeróbica pediría 50 s (deja de ser continuo).
_DATOS_DE_ZONA: dict[str, tuple[str, float, tuple[float, float]]] = {
    "R1":   ("Base aeróbica",       0.08, (5.0, 20.0)),
    "R2":   ("Umbral aeróbico",     0.15, (10.0, 30.0)),
    "MVO2": ("VO2 máximo",          0.50, (15.0, 90.0)),
    "RL":   ("Resistencia lactato", 1.50, (30.0, 240.0)),
    "V":    ("Velocidad pura",      3.50, (60.0, 300.0)),
}


class Zona(Enum):
    """Zona de entrenamiento. El orden de declaración es la jerarquía."""

    R1 = "R1"
    R2 = "R2"
    MVO2 = "MVO2"
    RL = "RL"
    V = "V"

    @classmethod
    def ordenadas(cls) -> tuple[Zona, ...]:
        """De la más lenta a la más rápida — el orden de siempre de la tabla."""
        return tuple(cls)

    @classmethod
    def desde_texto(cls, valor: str) -> Self:
        crudo = str(valor).strip().upper()
        for miembro in cls:
            if miembro.value.upper() == crudo:
                return miembro
        validos = ", ".join(m.value for m in cls)
        raise ValueError(f"Zona no reconocida: {valor!r}. Válidas: {validos}")

    @property
    def orden(self) -> int:
        """Posición en la jerarquía, 0 = la más lenta."""
        return tuple(type(self)).index(self)

    @property
    def etiqueta(self) -> str:
        return _DATOS_DE_ZONA[self.value][0]

    @property
    def ratio_descanso(self) -> float:
        """Descanso como fracción del tiempo de trabajo, antes de los topes."""
        return _DATOS_DE_ZONA[self.value][1]

    @property
    def limites_descanso_s(self) -> tuple[float, float]:
        return _DATOS_DE_ZONA[self.value][2]

    def descanso_para(self, trabajo: Tiempo) -> Duracion:
        """Descanso para una repetición que se nada en `trabajo`.

        `Duracion` y no `Tiempo`: un descanso es un hueco, no un nado. El
        prescrito siempre sale positivo (los suelos de la tabla lo garantizan),
        pero el descanso **real** de un parcial puede ser negativo cuando el
        nadador llega después de su salida, y los dos tienen que caber en el
        mismo tipo para poder compararse.
        """
        if not isinstance(trabajo, Tiempo):
            raise TypeError("El descanso se calcula sobre un Tiempo de trabajo")
        suelo, techo = self.limites_descanso_s
        return Duracion(min(max(trabajo.segundos * self.ratio_descanso, suelo), techo))

    def __lt__(self, otra: Zona) -> bool:
        if not isinstance(otra, Zona):
            return NotImplemented
        return self.orden < otra.orden

    def __le__(self, otra: Zona) -> bool:
        if not isinstance(otra, Zona):
            return NotImplemented
        return self.orden <= otra.orden

    def __gt__(self, otra: Zona) -> bool:
        if not isinstance(otra, Zona):
            return NotImplemented
        return self.orden > otra.orden

    def __ge__(self, otra: Zona) -> bool:
        if not isinstance(otra, Zona):
            return NotImplemented
        return self.orden >= otra.orden


# ── Zonas como factor sobre el RITMO DE CARRERA del evento ───────────────────
# zona_pace = ritmo_carrera × factor[perfil][distancia] (+ estilo) × piscina.
#   fondo:                 CALIBRADO (reproduce las zonas reales de Emiliano).
#   velocidad/medio fondo: SEED teórico, escalado validado con el pool nacional.
_FACTOR_SOBRE_RITMO: dict[Perfil, dict[int, dict[Zona, float]]] = {
    Perfil.VELOCIDAD: {
        50:  {Zona.R1: 1.562, Zona.R2: 1.417, Zona.MVO2: 1.285, Zona.RL: 1.165, Zona.V: 1.081},
        100: {Zona.R1: 1.419, Zona.R2: 1.288, Zona.MVO2: 1.168, Zona.RL: 1.059, Zona.V: 0.982},
    },
    Perfil.MEDIO_FONDO: {
        200: {Zona.R1: 1.150, Zona.R2: 1.108, Zona.MVO2: 1.073, Zona.RL: 0.987, Zona.V: 0.953},
        400: {Zona.R1: 1.093, Zona.R2: 1.053, Zona.MVO2: 1.020, Zona.RL: 0.938, Zona.V: 0.906},
    },
    Perfil.FONDO: {
        800:  {Zona.R1: 1.047, Zona.R2: 1.008, Zona.MVO2: 0.977, Zona.RL: 0.899, Zona.V: 0.868},
        1500: {Zona.R1: 1.020, Zona.R2: 0.982, Zona.MVO2: 0.952, Zona.RL: 0.876, Zona.V: 0.846},
    },
}


def factores_de_zona(perfil: Perfil, distancia: int) -> dict[Zona, float]:
    """Factores sobre el ritmo de carrera para (perfil, distancia)."""
    tabla = _FACTOR_SOBRE_RITMO[perfil]
    if distancia in tabla:
        return dict(tabla[distancia])
    cercana = min(tabla, key=lambda d: abs(d - distancia))
    return dict(tabla[cercana])


@dataclass(frozen=True, slots=True)
class Prescripcion:
    """Lo que se escribe en la pizarra para una zona: ritmo **y** salida.

    Invariante: `salida == trabajo + descanso`. Una prescripción cuyo descanso no
    cuadra con su salida es la forma exacta en que una zona se convierte en otra.
    """

    zona: Zona
    ritmo: Ritmo
    salida: Tiempo
    descanso: Duracion
    distancia_rep: int

    def __post_init__(self) -> None:
        if isinstance(self.distancia_rep, bool) or not isinstance(self.distancia_rep, int):
            raise TypeError("La distancia de repetición son metros enteros")
        if self.distancia_rep <= 0:
            raise ValueError("La distancia de repetición tiene que ser positiva")
        if not isinstance(self.descanso, Duracion):
            raise TypeError("El descanso de una prescripción es una Duracion, no un Tiempo")
        esperada = self.trabajo + self.descanso
        if abs(self.salida.segundos - esperada.segundos) > 1e-6:
            raise ValueError(
                f"La salida ({self.salida.texto()}) no es el trabajo más el descanso "
                f"({esperada.texto()}): esta serie no es la zona {self.zona.value}"
            )

    @classmethod
    def para(
        cls,
        zona: Zona,
        ritmo: Ritmo,
        distancia_rep: int = 100,
        *,
        paso_de_reloj: float = PASO_DE_RELOJ_S,
    ) -> Prescripcion:
        """Deriva la salida del ritmo de la zona, cuadrando al reloj de pared.

        Se redondea **hacia arriba**: hacia abajo recortaría el descanso, que es
        justo lo que la tabla de `Zona` dice que no se debe hacer.
        """
        trabajo = ritmo.a_tiempo(distancia_rep)
        salida = (trabajo + zona.descanso_para(trabajo)).al_reloj(paso_de_reloj)
        return cls(
            zona=zona,
            ritmo=ritmo,
            salida=salida,
            descanso=salida.diferencia(trabajo),
            distancia_rep=distancia_rep,
        )

    @property
    def trabajo(self) -> Tiempo:
        """Lo que se tarda en nadar una repetición a este ritmo."""
        return self.ritmo.a_tiempo(self.distancia_rep)

    @property
    def ratio_descanso_real(self) -> float:
        """Descanso : trabajo ya aplicados los topes y el cuadre al reloj."""
        return self.descanso.segundos / self.trabajo.segundos

    def texto(self, repeticiones: int | None = None) -> str:
        """`10 × 100 a 1:18 salida 1:30`. Las repeticiones son de presentación.

        Cuántas veces se repite **no** es parte de la prescripción: la misma zona
        al mismo ritmo son 10×400 en R1 y 8×25 en V. El número pertenece a la
        serie que se manda nadar (`Serie`, §5.11), y tenerlo aquí además de allí
        sería otra vez dos mitades de lo mismo separándose.
        """
        if repeticiones is not None and repeticiones <= 0:
            raise ValueError("Las repeticiones tienen que ser un número positivo")
        cabeza = f"{repeticiones} × " if repeticiones else ""
        return (
            f"{cabeza}{self.distancia_rep} a {self.trabajo.texto(0)} "
            f"salida {self.salida.texto(0)}"
        )

    def __str__(self) -> str:
        return self.texto()


@dataclass(frozen=True, slots=True)
class JuegoDeZonas(Mapping[Zona, "Prescripcion"]):
    """Las cinco prescripciones de una prueba. **No se persiste**: es derivado.

    Guardarlo crearía dato que queda mintiendo en cuanto el entrenador ajusta la
    meta. Lo que sí es un hecho —lo que se mandó nadar un día— es otra cosa.

    Es un `Mapping[Zona, Prescripcion]` de verdad, como pide el §3.3: hereda de
    `collections.abc` (stdlib, no infraestructura) y con eso gana `items()`,
    `keys()`, `values()`, `get()` y `dict(juego)`. Implementarlo a mano dejaba a
    cada consumidor iterando la lista de zonas **por fuera** del juego, que es la
    lista suelta que `Zona` existe para eliminar.
    """

    prueba: Prueba
    piscina: Piscina
    prescripciones: tuple[Prescripcion, ...]

    def __post_init__(self) -> None:
        zonas = [p.zona for p in self.prescripciones]
        if zonas != list(Zona.ordenadas()):
            raise ValueError(
                "Un juego de zonas lleva las cinco zonas, una vez y en orden: "
                f"llegaron {[z.value for z in zonas]}"
            )

    @classmethod
    def de(
        cls,
        ritmo_carrera: Ritmo,
        prueba: Prueba,
        piscina: Piscina = Piscina.LARGA,
        *,
        distancia_rep: int = 100,
    ) -> JuegoDeZonas:
        """Zonas ancladas al ritmo de carrera de la prueba.

            zona = (ritmo_carrera × factor[perfil][distancia] + estilo) × piscina
        """
        if not isinstance(ritmo_carrera, Ritmo):
            raise TypeError("Las zonas se anclan a un Ritmo de carrera")
        perfil = prueba.perfil_sugerido()
        factores = factores_de_zona(perfil, prueba.distancia)
        correccion = prueba.estilo.correccion_tpace_s
        factor_piscina = piscina.factor(perfil)
        objetivos = (
            Ritmo((ritmo_carrera.segundos_por_100 * factores[zona] + correccion) * factor_piscina)
            for zona in Zona.ordenadas()
        )
        return cls(
            prueba=prueba,
            piscina=piscina,
            prescripciones=tuple(
                Prescripcion.para(zona, objetivo, distancia_rep)
                for zona, objetivo in zip(Zona.ordenadas(), objetivos, strict=True)
            ),
        )

    def __getitem__(self, zona: Zona) -> Prescripcion:
        # KeyError y no AttributeError: es el contrato de Mapping, y de él
        # dependen `get()` y el `__contains__` heredado.
        if not isinstance(zona, Zona):
            raise KeyError(zona)
        return self.prescripciones[zona.orden]

    def __iter__(self) -> Iterator[Zona]:
        return iter(Zona.ordenadas())

    def __len__(self) -> int:
        return len(self.prescripciones)

    def ritmo_de(self, zona: Zona) -> Ritmo:
        return self[zona].ritmo

    def texto(self) -> str:
        return "\n".join(f"{p.zona.value:>4}  {p.texto()}" for p in self.prescripciones)
