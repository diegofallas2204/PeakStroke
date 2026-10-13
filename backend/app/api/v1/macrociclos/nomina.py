"""Quién está inscrito en el macrociclo: meterlo, sacarlo y devolverlo.

La regla de **un atleta, un macrociclo vivo** no está aquí sino en
`inscripcion.py`, y la impone el router antes de llamar a `add_athlete` /
`restore_athlete`. Aquí solo está el efecto sobre la inscripción, incluido el
que importa: **sacar a alguien es darle de baja, nunca borrarlo**.

Desde C9 (2026-10-05) la inscripción es una entidad: se crea con
`Macrociclo.inscribir()` —que exige una ficha de su club y activa—, se saca y se
devuelve con `dar_de_baja()` / `restaurar()` (idempotentes) y se guarda por
`RepositorioDeInscripciones.guardar`.

Y desde el punto 3 (2026-10-13) sus pruebas también: aquí se construye cada
`PruebaObjetivo` y se le pide al motor su plan; las filas las arma el
repositorio. **Este archivo ya no importa ninguna tabla**, y
`tests/test_prueba_objetivo_api.py` lo comprueba. Cada semana que devuelve el
motor se convierte aquí en una `Semana` (punto 4): lo que se guarda de ella es
su fecha, sus kilómetros, su tiempo esperado y su fase.
"""
from __future__ import annotations

from app.dominio.entidades import (
    Atleta,
    Inscripcion,
    InscripcionImposible,
    Macrociclo,
    PruebaObjetivo,
    Semana,
)
from app.dominio.servicios.motor import MOTOR
from app.dominio.valores import Ritmo, Tiempo
from app.persistencia.repositorios import RepositorioDeAtletas, RepositorioDeInscripciones

from .schemas import AddAthleteRequest


def _pruebas(
    macro: Macrociclo, atleta: Atleta, data: AddAthleteRequest,
) -> list[tuple[PruebaObjetivo, list[Semana]]]:
    """Sus pruebas objetivo, cada una con el plan semanal que le genera el motor."""
    phases = [
        {"name": f.nombre, "type": f.fase.value,
         "week_start": f.semana_inicio, "week_end": f.semana_fin}
        for f in macro.fases
    ]
    # Edad al inicio del macro: ajusta al alza el techo I_max de menores (juventud).
    edad = atleta.edad_en(macro.inicio)
    pruebas = []
    for e in data.events:
        # El estilo sale canónico de la entidad («crol» → «libre»): es el que
        # se guarda y el que recibe el motor, que no distingue uno del otro.
        prueba = e.a_entidad()
        semanas = MOTOR.generar_plan(
            distancia=prueba.prueba.distancia, tiempo_actual=prueba.actual.segundos,
            tiempo_meta=prueba.meta.segundos, semanas=macro.semanas,
            km_totales=macro.km_totales, curva=macro.curva,
            inicio=macro.inicio, semanas_por_micro=macro.semanas_por_micro,
            fases=phases or None, estilo=prueba.prueba.estilo.value,
            piscina=macro.piscina.value, n_mac=macro.n_mac, edad=edad,
            # El nivel sale del test aeróbico cuando la inscripción lo trae: es
            # el dato para el que la tabla de niveles está calibrada. Derivarlo
            # del ritmo de carrera deja un borde de una décima que mueve el
            # volumen un 45 % (defecto 1 de §10.4).
            base_aerobica=data.aerobic_base,
        )
        pruebas.append((prueba, [
            Semana(
                numero=s.numero, fecha=s.fecha, km_planificados=s.km,
                esperado=Tiempo(s.tiempo_esperado), fase=s.fase,
            )
            for s in semanas
        ]))
    return pruebas


async def add_athlete(
    repo: RepositorioDeInscripciones, macro: Macrociclo, atleta: Atleta,
    data: AddAthleteRequest,
) -> Inscripcion:
    """Inscribe al atleta con sus pruebas, todo en una transacción.

    Devuelve la inscripción ya guardada (con su `id`).

    `InscripcionImposible` (ficha de baja o de otro club) sube al router: 409.
    """
    # Una base que no es un ritmo (0, negativa) entra como «sin base», como
    # antes de C9: cambiarlo a un 422 no era decisión de este bloque.
    base = Ritmo(data.aerobic_base) if data.aerobic_base and data.aerobic_base > 0 else None
    inscripcion = macro.inscribir(atleta, base, data.aerobic_base_source)
    fila = await repo.guardar(inscripcion, pruebas=_pruebas(macro, atleta, data))
    assert fila is not None   # una inscripción nueva siempre es del equipo de quien la crea
    return inscripcion


async def remove_athlete(
    repo: RepositorioDeInscripciones, plan_id: int, athlete_plan_id: int,
) -> bool | None:
    """Saca al atleta del macrociclo. **Da de baja la inscripción, no la borra.**

    Hasta el 2026-08-07 hacía `db.delete(ap)`, y `AthletePlan` cascadea a
    `athlete_events` y de ahí a `weekly_plans`: se llevaba las 12 semanas del
    atleta y todos los tiempos reales que había registrado.

    `None` si no existe, no es visible o es de otro macrociclo (el router: 404).
    Si no, si cambió algo: sacar a quien ya estaba fuera no falla.
    """
    inscripcion = await repo.por_id(athlete_plan_id)
    if inscripcion is None or inscripcion.macrociclo_id != plan_id:
        return None
    cambio = inscripcion.dar_de_baja()
    if cambio:
        await repo.guardar(inscripcion)
    return cambio


async def restore_athlete(
    repo: RepositorioDeInscripciones, atletas: RepositorioDeAtletas,
    plan_id: int, athlete_plan_id: int,
) -> bool | None:
    """Vuelve a inscribir a un atleta dado de baja, con su histórico intacto.

    Sin esta puerta, la baja lógica de arriba sería un borrado con otro nombre.
    Mismo contrato que `remove_athlete`: `None` es 404, si no, si cambió algo.

    **Devolver es inscribir otra vez**: la ficha tiene que seguir activa, o el
    restore sería la puerta trasera de lo que `Macrociclo.inscribir` cierra por
    delante (`InscripcionImposible`, el 409).
    """
    inscripcion = await repo.por_id(athlete_plan_id)
    if inscripcion is None or inscripcion.macrociclo_id != plan_id:
        return None
    atleta = await atletas.por_id(inscripcion.atleta_id)
    if inscripcion.activa is False and (atleta is None or not atleta.activo):
        raise InscripcionImposible(
            f"La ficha de {atleta or 'ese atleta'} está dada de baja: "
            "restáurala antes de devolverla al macrociclo",
        )
    cambio = inscripcion.restaurar()
    if cambio:
        await repo.guardar(inscripcion)
    return cambio
