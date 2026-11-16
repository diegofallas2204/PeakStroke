"""Qué dicen los números de un test de lactato: la lectura para el entrenador.

Cada hallazgo sale de una regla con respaldo, no de una impresión:

- **Zona**: la mediana del lactato frente al rango de la zona pedida
  (`Zona.rango_de_lactato`, nota 03).
- **Estado estable** (MLSS): el lactato no sube más de 1 mmol/L en la segunda
  mitad. Si sube más, la intensidad está por encima del máximo estable.
- **Ritmo**: frente al tiempo propuesto. Más rápido y aun así en zona y estable
  quiere decir que el propuesto le queda holgado o que su marca está vieja (la
  mitad del grupo del 22/09, nota 26).
- **Intensidad**: el % de su mejor marca frente a la «Intens. Pro» pedida.
- **Técnica**: con fatiga, a la misma velocidad sube la frecuencia y baja la
  longitud de ciclo (más brazadas por tramo). Con el lactato estable eso apunta
  a fatiga técnica o muscular, no metabólica. El índice de ciclo (Costill,
  1985) es el indicador de economía.
- **Serie**: una pendiente clara significa que no fue pareja (descendente =
  buscó el ritmo; ascendente = se fue cayendo).
- **Recuperación**: el pico llega unos minutos después del esfuerzo; cuánto baja
  desde ahí es el aclaramiento.

**Describe, no diagnostica.** El mismo % de la mejor marca es otra zona en cada
nadador (nota 26), y una muestra puede estar contaminada: los avisos de calidad
van aparte (`avisos_de_lactato.py`) y conviene leerlos primero.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..entidades import TestDeLactato
from ..valores import EstadoDeZona, Tiempo

DERIVA_TECNICA_PCT = 10.0      # brazadas: a partir de aquí es pérdida de longitud
TECNICA_ESTABLE_PCT = 5.0
RITMO_PAREJO_CV = 2.0          # % de CV para decir «al mismo ritmo»
PENDIENTE_CLARA = 1.0          # s por repetición
MARGEN_PROPUESTO = 2.0         # s: dentro de esto, «en el propuesto»

Tono = Literal["bien", "atencion", "info"]


@dataclass(frozen=True, slots=True)
class Hallazgo:
    tipo: str        # zona | estado_estable | ritmo | intensidad | tecnica | serie | recuperacion
    tono: Tono
    mensaje: str


def _reloj(segundos: float) -> str:
    return Tiempo(segundos).texto(0)


def lectura(test: TestDeLactato) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    zona = test.zona.value
    mediana = test.lactato_mediano()
    estado = test.estado_de_zona(mediana) if mediana is not None else None
    rango = test.zona.rango_de_lactato

    if estado is not None and rango is not None:
        texto_rango = f"{rango[0]}–{rango[1]}" if rango[1] is not None else f"más de {rango[0]}"
        hallazgos.append({
            EstadoDeZona.DENTRO: Hallazgo("zona", "bien",
                f"El lactato quedó en {zona}: mediana {mediana} mmol/L ({texto_rango})."),
            EstadoDeZona.ENCIMA: Hallazgo("zona", "atencion",
                f"Por encima de {zona}: mediana {mediana} mmol/L ({texto_rango}). "
                "La serie fue más intensa que la zona pedida."),
            EstadoDeZona.DEBAJO: Hallazgo("zona", "info",
                f"Por debajo de {zona}: mediana {mediana} mmol/L ({texto_rango}). "
                "La serie fue más suave que la zona pedida."),
        }[estado])

    estable = test.estado_estable()
    subida = test.subida_en_la_segunda_mitad()
    if estable is True:
        hallazgos.append(Hallazgo("estado_estable", "bien",
            f"Estado estable: el lactato cambió {subida:+.1f} mmol/L en la segunda mitad (≤ 1)."))
    elif estable is False:
        hallazgos.append(Hallazgo("estado_estable", "atencion",
            f"Sin estado estable: el lactato subió {subida:+.1f} mmol/L en la segunda mitad. "
            "La intensidad está por encima de la que puede sostener."))

    diferencia = test.diferencia_con_propuesto()
    if diferencia is not None:
        if abs(diferencia) <= MARGEN_PROPUESTO:
            hallazgos.append(Hallazgo("ritmo", "bien", "Nadó en el tiempo propuesto."))
        elif diferencia < 0:
            if estado is EstadoDeZona.DENTRO and estable is not False:
                hallazgos.append(Hallazgo("ritmo", "info",
                    f"Nadó {-diferencia:.1f} s más rápido que lo propuesto y aun así en zona: "
                    "el propuesto le queda holgado, o su marca de referencia está desactualizada."))
            elif estado is EstadoDeZona.ENCIMA or estable is False:
                hallazgos.append(Hallazgo("ritmo", "atencion",
                    f"Nadó {-diferencia:.1f} s más rápido que lo propuesto y se salió de la zona: "
                    "el ritmo pedido era el adecuado."))
            else:
                hallazgos.append(Hallazgo("ritmo", "info",
                    f"Nadó {-diferencia:.1f} s más rápido que lo propuesto."))
        else:
            hallazgos.append(Hallazgo("ritmo", "info",
                f"Nadó {diferencia:.1f} s más lento que lo propuesto."))

    intensidad = test.estado_de_intensidad()
    if intensidad is not None:
        real = test.pct_de_referencia()
        bajo, alto = test.intensidad_propuesta   # type: ignore[misc]
        pedido = f"se pidió {bajo:g}–{alto:g} %"
        hallazgos.append({
            EstadoDeZona.DENTRO: Hallazgo("intensidad", "bien", f"Nadó al {real:.1f} % de su mejor marca; {pedido}."),
            EstadoDeZona.ENCIMA: Hallazgo("intensidad", "atencion",
                f"Nadó al {real:.1f} % de su mejor marca, por encima de lo pedido ({pedido})."),
            EstadoDeZona.DEBAJO: Hallazgo("intensidad", "info",
                f"Nadó al {real:.1f} % de su mejor marca, por debajo de lo pedido ({pedido})."),
        }[intensidad])

    deriva = test.deriva_de_brazada_pct()
    if deriva is not None:
        if deriva > DERIVA_TECNICA_PCT and test.cv_pct() < RITMO_PAREJO_CV:
            causa = ("Con el lactato estable, apunta a fatiga técnica o muscular, no metabólica."
                     if estable is not False else "Con el lactato subiendo, es fatiga general.")
            hallazgos.append(Hallazgo("tecnica", "atencion",
                f"Las brazadas subieron un {deriva:.0f} % al mismo ritmo: sostuvo la velocidad subiendo "
                f"la frecuencia porque perdió longitud de ciclo. {causa}"))
        elif abs(deriva) <= TECNICA_ESTABLE_PCT:
            hallazgos.append(Hallazgo("tecnica", "bien",
                f"Técnica estable: las brazadas cambiaron {deriva:+.0f} % en la serie."))

    pendiente = test.pendiente()
    tiempos = test.tiempos()
    if pendiente <= -PENDIENTE_CLARA:
        hallazgos.append(Hallazgo("serie", "info",
            f"Serie descendente ({_reloj(tiempos[0])} → {_reloj(tiempos[-1])}): las primeras repeticiones "
            "fueron de buscar el ritmo; para la zona cuentan más las del tramo estable."))
    elif pendiente >= PENDIENTE_CLARA:
        hallazgos.append(Hallazgo("serie", "atencion",
            f"Se fue haciendo más lenta ({_reloj(tiempos[0])} → {_reloj(tiempos[-1])}): señal de fatiga; "
            "puede que saliera demasiado rápido."))

    pico = test.pico_de_recuperacion()
    if pico is not None:
        minuto, valor = pico
        mensaje = f"Pico de {valor} mmol/L en el min {minuto:g} de recuperación"
        aclarado = test.aclaramiento_pct()
        if aclarado is not None:
            ultimo = test.recuperacion[-1].minuto
            mensaje += (f"; en el min {ultimo:g} había bajado un {aclarado:.0f} % "
                        f"({test.tasa_de_aclaramiento():.2f} mmol/L por minuto)")
        hallazgos.append(Hallazgo("recuperacion", "info", mensaje + "."))

    return hallazgos
