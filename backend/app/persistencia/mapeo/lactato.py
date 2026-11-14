"""Test de lactato: fila ↔ entidad, en las dos direcciones.

Construir la entidad **es** validar: un lactato negativo, unas brazadas sin
tramo o un propuesto al revés no llegan a fila, porque `fila_de_test_de_lactato`
solo acepta una entidad ya construida.
"""
from __future__ import annotations

from enum import Enum

from app.dominio.entidades import ProtocoloDeMuestra, Repeticion, TestDeLactato
from app.dominio.valores import (
    MetodoDeFc,
    ModoDeLactato,
    SitioDeMuestra,
    Tiempo,
    TipoDeDescanso,
    Zona,
)
from app.persistencia.tablas.tests_de_lactato import LactateRep, LactateTest


def _o_none(enum: type[Enum], valor: str | None) -> Enum | None:
    return enum.desde_texto(valor) if valor is not None else None


def test_de_lactato_desde_fila(fila: LactateTest) -> TestDeLactato:
    propuesto = (
        (fila.proposed_min, fila.proposed_max)
        if fila.proposed_min is not None and fila.proposed_max is not None else None
    )
    return TestDeLactato(
        id=fila.id, atleta_id=fila.swimmer_id, fecha=fila.test_date,
        modo=ModoDeLactato.desde_texto(fila.mode), zona=Zona.desde_texto(fila.target_zone),
        distancia_rep=fila.rep_distance,
        descanso=_o_none(TipoDeDescanso, fila.rest_type), descanso_s=fila.rest_s,
        propuesto=propuesto, referencia=fila.reference_time, tramo_m=fila.counted_segment_m,
        protocolo=ProtocoloDeMuestra(
            sitio=_o_none(SitioDeMuestra, fila.sample_site), analizador=fila.analyzer,
            minuto=fila.sample_minute, metodo_fc=_o_none(MetodoDeFc, fila.hr_method),
        ),
        notas=fila.notes, activo=fila.is_active,
        repeticiones=[
            Repeticion(
                r.rep_number, Tiempo(r.swim_time), lactato=r.lactate, fc=r.heart_rate,
                esfuerzo=r.effort, brazadas=tuple(r.stroke_counts or ()),
                tiempo_tramo=Tiempo(r.segment_time) if r.segment_time else None,
            )
            for r in fila.reps
        ],
    )


def fila_de_test_de_lactato(test: TestDeLactato, *, team_id: int) -> LactateTest:
    p = test.protocolo
    fila = LactateTest(
        team_id=team_id, swimmer_id=test.atleta_id, test_date=test.fecha,
        mode=test.modo.value, target_zone=test.zona.value, rep_distance=test.distancia_rep,
        rest_type=test.descanso.value if test.descanso else None, rest_s=test.descanso_s,
        proposed_min=test.propuesto[0] if test.propuesto else None,
        proposed_max=test.propuesto[1] if test.propuesto else None,
        reference_time=test.referencia, counted_segment_m=test.tramo_m,
        sample_site=p.sitio.value if p.sitio else None, analyzer=p.analizador,
        sample_minute=p.minuto, hr_method=p.metodo_fc.value if p.metodo_fc else None,
        notes=test.notas, is_active=test.activo,
    )
    fila.reps = [
        LactateRep(
            rep_number=r.numero, swim_time=round(r.tiempo.segundos, 2), lactate=r.lactato,
            heart_rate=r.fc, effort=r.esfuerzo,
            stroke_counts=list(r.brazadas) or None,
            segment_time=r.tiempo_tramo.segundos if r.tiempo_tramo else None,
        )
        for r in test.repeticiones
    ]
    return fila
