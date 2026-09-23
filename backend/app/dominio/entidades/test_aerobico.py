"""El test aeróbico, con la conversión reloj→nadado dentro del constructor.

Esta es la razón de ser del paso 2. Hoy *«en la base de datos siempre se guarda
el tiempo NADADO»* es una regla escrita en `CLAUDE.md` y en la nota 19 del vault
que alguien tiene que **acordarse** de aplicar en `create_test`. Olvidarla es lo
que produjo una base aeróbica un 114 % más alta que la real (169 s/100 m frente a
79), y de una base aeróbica cuelgan las zonas, la predicción semanal y la
factibilidad: es el error más caro que ha tenido la aplicación.

Aquí no hay nada que recordar. El constructor recibe **lo que apuntó el
entrenador** y el modo en que lo apuntó, y lo que queda construido son parciales
con el tiempo nadado ya despejado. No existe una segunda puerta: `Parcial` no se
puede pasar hecho desde fuera, así que no hay forma de tener en las manos un
`TestAerobico` cuyos parciales sean llegadas de reloj sin convertir. La regla
deja de ser documentación y pasa a ser una invariante del tipo.

    TestAerobico(tipo=T30, fecha=…, salida=Tiempo(90), modo=CLOCK,
                 numeros=[78.0, 169.0, 260.0])   ← llegadas del reloj
    → parciales nadados 78.0 · 79.0 · 80.0       ← lo que se guarda

**Las salidas son fijas, no encadenadas.** La repetición n sale en (n−1)·S aunque
la anterior se pasara del intervalo: el reloj no espera a nadie. Modelarlo como
«sale cuando llega el anterior» sería analizar un test distinto del que se nadó,
y no llegar a tiempo es un dato del atleta sobre ese intervalo, no un error de
captura — por eso un descanso negativo se registra en vez de rechazarse.

Recupera el análisis de `engine/aerobic.py::analyze_splits` (§8 del mapa de
traducción). Mientras esa función siga teniendo llamadores conviven las dos, y
`tests/test_entidades_vs_motor.py` fija que dan exactamente los mismos números.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from ..valores import Duracion, ModoDeIngreso, Ritmo, Tendencia, Tiempo, TipoDeTest
from .base import PorIdentidad

# Pendiente (s/100 m por repetición) a partir de la cual el test se considera en
# mejora o en caída en lugar de estable.
PENDIENTE_DE_TENDENCIA = 0.05


@dataclass(frozen=True, slots=True)
class Parcial:
    """Una repetición del test. `tiempo_nadado` es siempre el tiempo de nado.

    `inicio` es el segundo en que ARRANCA la repetición contado desde el inicio
    del test, y es una `Duracion` porque el de la primera vale exactamente 0 —un
    `Tiempo` es siempre positivo—. Es opcional porque los tests guardados antes
    de que existiera el intervalo de salida no lo pueden saber a posteriori: sin
    él el test sigue siendo válido, solo pierde el descanso y la densidad.
    """

    numero: int
    tiempo_nadado: Tiempo
    inicio: Duracion | None = None

    def llegada(self) -> Tiempo | None:
        """Lo que marcaba el reloj de pared al tocar la pared."""
        if self.inicio is None:
            return None
        return self.tiempo_nadado + self.inicio

    def descanso_hasta(self, siguiente: Parcial) -> Duracion | None:
        """Cuánto se descansa entre tocar la pared y la salida de la siguiente.

        Negativo cuando la repetición se pasó del intervalo. No es un error: es
        el hecho que hay que registrar.
        """
        llegada = self.llegada()
        if llegada is None or siguiente.inicio is None:
            return None
        return siguiente.inicio - llegada.a_duracion()


class TestAerobico(PorIdentidad):
    """Un test aeróbico con parciales (T-30, T-15 o personalizado N×D).

    Los tests sin parciales —CSS, ingreso directo— no pasan por aquí: su base
    aeróbica no se analiza, se calcula de otra cosa o la escribe el entrenador.
    """

    # Un "test" aquí es una medición del atleta, no una prueba automatizada.
    # Sin esto, pytest intenta recolectar la clase cada vez que un test la
    # importa y avisa de que no puede (tiene `__init__`). El nombre lo fija
    # `docs/REDISENO.md` §5.9 y es el del dominio; el que se aparta del suyo es
    # pytest.
    __test__ = False

    __slots__ = (
        "activo",
        "atleta_id",
        "distancia_rep",
        "fecha",
        "id",
        "macrociclo_id",
        "modo",
        "notas",
        "parciales",
        "salida",
        "tipo",
    )

    def __init__(
        self,
        *,
        tipo: TipoDeTest,
        fecha: date,
        numeros: Sequence[float],
        distancia_rep: int = 100,
        salida: Tiempo | float | None = None,
        modo: ModoDeIngreso = ModoDeIngreso.REP,
        id: int | None = None,
        atleta_id: int | None = None,
        macrociclo_id: int | None = None,
        notas: str | None = None,
        activo: bool = True,
    ) -> None:
        """`numeros` es lo que apuntó el entrenador, leído según `modo`.

        En modo `REP` son tiempos de nado y entran tal cual; en modo `CLOCK` son
        llegadas acumuladas del reloj y se convierten aquí, una vez.
        """
        if not numeros:
            raise ValueError("Se requiere al menos un parcial")
        if not isinstance(tipo, TipoDeTest):
            raise TypeError(f"El tipo de test es un TipoDeTest, no {type(tipo).__name__}")
        if not isinstance(modo, ModoDeIngreso):
            raise TypeError(f"El modo de ingreso es un ModoDeIngreso, no {type(modo).__name__}")
        if not tipo.tiene_parciales:
            raise ValueError(
                f"Un test {tipo.value} no se analiza por parciales: su base aeróbica "
                "sale del cálculo CSS o la escribe el entrenador",
            )

        # Un T-30 son repeticiones de 100 por definición. Aceptar otra distancia
        # produce una base que no es comparable con ningún otro T-30, así que el
        # tipo manda sobre lo que venga en la petición (la regla vivía suelta en
        # `aerobic_tests/service.py`: `100 if test_type in ("T30", "T15")`).
        fija = tipo.distancia_rep_fija
        distancia_rep = fija if fija is not None else int(distancia_rep)
        if distancia_rep <= 0:
            raise ValueError("La distancia de repetición debe ser positiva")

        if salida is not None and not isinstance(salida, Tiempo):
            if salida <= 0:
                raise ValueError("El intervalo de salida debe ser positivo")
            salida = Tiempo(salida)
        if salida is None and modo.es_acumulado:
            raise ValueError(
                "Las llegadas de reloj necesitan el intervalo de salida "
                "para despejar el tiempo nadado",
            )

        self.id = id
        self.atleta_id = atleta_id
        self.macrociclo_id = macrociclo_id
        self.tipo = tipo
        self.fecha = fecha
        self.distancia_rep = distancia_rep
        self.salida = salida
        self.modo = modo
        self.notas = notas
        self.activo = activo
        self.parciales: tuple[Parcial, ...] = self._construir_parciales(numeros, salida, modo)

    @staticmethod
    def _construir_parciales(
        numeros: Sequence[float], salida: Tiempo | None, modo: ModoDeIngreso,
    ) -> tuple[Parcial, ...]:
        """Donde ocurre la conversión. El único sitio que fabrica `Parcial`."""
        parciales: list[Parcial] = []
        for indice, numero in enumerate(numeros):
            if salida is None:
                parciales.append(Parcial(indice + 1, Tiempo(numero)))
                continue
            inicio = Duracion(indice * salida.segundos)
            if not modo.es_acumulado:
                parciales.append(Parcial(indice + 1, Tiempo(numero), inicio))
                continue
            nadado = round(numero - inicio.segundos, 3)
            if nadado <= 0:
                raise ValueError(
                    f"La llegada de la repetición {indice + 1} es anterior a su salida: "
                    "revisa el intervalo o el modo de ingreso",
                )
            parciales.append(Parcial(indice + 1, Tiempo(nadado), inicio))
        return tuple(parciales)

    # ── Lo que se nadó ───────────────────────────────────────────────────────

    @property
    def repeticiones(self) -> int:
        return len(self.parciales)

    def tiempos_nadados(self) -> list[Tiempo]:
        return [p.tiempo_nadado for p in self.parciales]

    def parciales_por_100(self) -> list[Ritmo]:
        """Cada repetición normalizada a s/100 m, la unidad central del sistema."""
        factor = self.distancia_rep / 100.0
        return [Ritmo(round(p.tiempo_nadado.segundos / factor, 2)) for p in self.parciales]

    def base_aerobica(self) -> Ritmo:
        """El ritmo medio del test: la base aeróbica del atleta."""
        por_100 = [r.segundos_por_100 for r in self.parciales_por_100()]
        return Ritmo(round(sum(por_100) / len(por_100), 2))

    def consistencia(self) -> float:
        """Desviación típica de los parciales (s/100 m). Menos es más parejo."""
        por_100 = [r.segundos_por_100 for r in self.parciales_por_100()]
        media = sum(por_100) / len(por_100)
        varianza = sum((t - media) ** 2 for t in por_100) / len(por_100)
        return round(math.sqrt(varianza), 3)

    def pendiente(self) -> float:
        """s/100 m que gana o pierde cada repetición. Negativo = va mejorando."""
        return round(_pendiente_lineal([r.segundos_por_100 for r in self.parciales_por_100()]), 4)

    def tendencia(self) -> Tendencia:
        """Si el atleta aguantó, se fue soltando o se fue cayendo."""
        pendiente = _pendiente_lineal([r.segundos_por_100 for r in self.parciales_por_100()])
        if pendiente <= -PENDIENTE_DE_TENDENCIA:
            return Tendencia.MEJORANDO
        if pendiente >= PENDIENTE_DE_TENDENCIA:
            return Tendencia.EMPEORANDO
        return Tendencia.ESTABLE

    # ── Lo que aporta el intervalo de salida ─────────────────────────────────

    def se_nado_sobre_intervalo(self) -> bool:
        return self.salida is not None

    def descansos(self) -> list[Duracion]:
        """Descanso real de cada repetición. Vacío si no hubo intervalo.

        Es `S − t`, y sale negativo cuando la repetición se pasó del intervalo.
        """
        if self.salida is None:
            return []
        return [
            Duracion(round(self.salida.segundos - p.tiempo_nadado.segundos, 2))
            for p in self.parciales
        ]

    def descanso_medio(self) -> Duracion | None:
        descansos = self.descansos()
        if not descansos:
            return None
        return Duracion(round(sum(d.segundos for d in descansos) / len(descansos), 2))

    def trabajo_medio(self) -> Tiempo:
        return Tiempo(sum(p.tiempo_nadado.segundos for p in self.parciales) / self.repeticiones)

    def ratio_descanso_trabajo(self) -> float | None:
        """Descanso medio partido por trabajo medio. La forma en que se prescribe."""
        medio = self.descanso_medio()
        if medio is None:
            return None
        return round(medio.segundos / self.trabajo_medio().segundos, 4)

    def densidad(self) -> float | None:
        """Fracción del ciclo que es nado: trabajo / (trabajo + descanso).

        Con salidas fijas ese denominador **es** el intervalo, así que la
        densidad es trabajo medio / salida. Es lo que distingue dos series al
        mismo ritmo que no entrenan lo mismo.
        """
        if self.salida is None:
            return None
        return round(self.trabajo_medio().segundos / self.salida.segundos, 4)

    def intervalos_perdidos(self) -> list[int]:
        """Números de repetición (1..N) que no llegaron dentro de su intervalo."""
        return [i + 1 for i, d in enumerate(self.descansos()) if d.es_negativa()]

    def __str__(self) -> str:
        return f"{self.tipo.value} {self.repeticiones}×{self.distancia_rep} ({self.fecha})"


def _pendiente_lineal(valores: list[float]) -> float:
    """Pendiente de regresión lineal simple sobre el índice de repetición."""
    n = len(valores)
    if n < 2:
        return 0.0
    media_x = (n - 1) / 2
    media_y = sum(valores) / n
    numerador = sum((i - media_x) * (v - media_y) for i, v in enumerate(valores))
    denominador = sum((i - media_x) ** 2 for i in range(n))
    return numerador / denominador if denominador else 0.0
