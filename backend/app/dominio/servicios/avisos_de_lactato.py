"""Los avisos de calidad del test de lactato. **Avisan, no bloquean.**

Salen de lo que pasó el 22/09 (nota 26, «Calidad del dato»): una muestra con
sudor o agua, una FC tomada tarde en la pausa, una repetición mal apuntada. Un
dato raro puede ser fisiología real, así que el test se guarda igual; lo que
hace el aviso es que nadie saque una conclusión de él sin mirarlo.

Las cuatro reglas:

1. Lactato por debajo de 1.0 mmol/L en esfuerzo: por debajo del reposo típico.
2. Una muestra que se aparta más de 3 mmol/L de la mediana de las demás, o un
   salto de más de 3 mmol/L entre dos muestras seguidas, a ritmo parecido.
3. FC que cae más de 20 lat/min respecto a su máximo hasta ahí mientras el
   esfuerzo no baja.
4. Una repetición más de un 10 % más lenta que la mediana de la serie.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from ..entidades import Repeticion, TestDeLactato

LACTATO_MINIMO_EN_ESFUERZO = 1.0
SALTO_DE_LACTATO = 3.0
CAIDA_DE_FC = 20
LENTITUD = 0.10
# «Ritmo parecido» entre dos repeticiones: menos de esto de diferencia.
RITMO_PARECIDO = 0.05


@dataclass(frozen=True, slots=True)
class Aviso:
    repeticion: int
    campo: str        # tiempo | lactato | fc
    mensaje: str


def avisos(test: TestDeLactato) -> list[Aviso]:
    encontrados: dict[tuple[int, str], Aviso] = {}

    def apuntar(rep: int, campo: str, mensaje: str) -> None:
        encontrados.setdefault((rep, campo), Aviso(rep, campo, mensaje))

    reps = {r.numero: r for r in test.repeticiones}
    mediana_t = statistics.median(test.tiempos())
    lentas = {n for n, r in reps.items() if r.tiempo.segundos > mediana_t * (1 + LENTITUD)}

    for n in sorted(lentas):
        lenta = _pct(reps[n].tiempo.segundos / mediana_t - 1)
        apuntar(n, "tiempo", f"Un {lenta} más lenta que la mediana: ¿pasó algo o está mal apuntada?")

    muestras = test.muestras()
    for n, valor in muestras:
        if valor < LACTATO_MINIMO_EN_ESFUERZO:
            apuntar(n, "lactato", f"Muestra de {valor} mmol/L, por debajo del reposo: revísala")
    if len(muestras) >= 3:
        for n, valor in muestras:
            if n in lentas:
                continue
            resto = statistics.median(v for m, v in muestras if m != n)
            if abs(valor - resto) > SALTO_DE_LACTATO:
                apuntar(n, "lactato", f"La muestra de {valor} mmol/L no cuadra con el resto "
                                      f"(mediana {resto}): posible contaminación")
    for (n1, v1), (n2, v2) in zip(muestras, muestras[1:], strict=False):
        if abs(v2 - v1) > SALTO_DE_LACTATO and _parecidas(reps[n1], reps[n2]):
            for n in (n1, n2):
                apuntar(n, "lactato", f"Salto de {v1} a {v2} mmol/L entre repeticiones al mismo ritmo")

    maxima: Repeticion | None = None
    for r in test.repeticiones:
        if r.fc is None:
            continue
        if maxima is not None and maxima.fc - r.fc > CAIDA_DE_FC \
                and r.esfuerzo is not None and maxima.esfuerzo is not None \
                and r.esfuerzo >= maxima.esfuerzo:
            apuntar(r.numero, "fc", f"La FC cae de {maxima.fc} a {r.fc} mientras el esfuerzo "
                                    "no baja: revisa cómo se midió")
        if maxima is None or r.fc > maxima.fc:
            maxima = r

    return sorted(encontrados.values(), key=lambda a: (a.repeticion, a.campo))


def _parecidas(a: Repeticion, b: Repeticion) -> bool:
    return abs(a.tiempo.segundos - b.tiempo.segundos) / min(a.tiempo.segundos, b.tiempo.segundos) <= RITMO_PARECIDO


def _pct(fraccion: float) -> str:
    return f"{fraccion * 100:.0f} %"
