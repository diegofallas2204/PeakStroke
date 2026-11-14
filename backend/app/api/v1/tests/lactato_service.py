"""Construir el test de lactato desde la petición y pintarlo hacia fuera.

Lo derivado sale siempre de la entidad (`dominio/entidades/test_de_lactato.py`)
y de los avisos (`dominio/servicios/avisos_de_lactato.py`): aquí solo se redondea
y se da forma. Nada se guarda calculado.
"""
from __future__ import annotations

from app.core.principal import Principal
from app.dominio.entidades import ProtocoloDeMuestra, Repeticion, TestDeLactato
from app.dominio.servicios.avisos_de_lactato import avisos
from app.dominio.valores import (
    MetodoDeFc,
    ModoDeLactato,
    SitioDeMuestra,
    Tiempo,
    TipoDeDescanso,
    Zona,
)
from app.persistencia.mapeo.lactato import fila_de_test_de_lactato, test_de_lactato_desde_fila
from app.persistencia.repositorios import RepositorioDeAtletas, RepositorioDeTestsDeLactato
from app.persistencia.tablas.tests_de_lactato import LactateTest

from .lactato_schemas import (
    LactateAnalysis,
    LactateRepOut,
    LactateSummary,
    LactateTestCreate,
    LactateTestResponse,
    LactateWarning,
)


def _r(valor: float | None, decimales: int = 2) -> float | None:
    return round(valor, decimales) if valor is not None else None


def entidad_desde_peticion(data: LactateTestCreate) -> TestDeLactato:
    """`ValueError` si no cuadra (el router: 422). La entidad es la que valida."""
    if (data.proposed_min is None) != (data.proposed_max is None):
        raise ValueError("El tiempo propuesto lleva sus dos extremos")
    return TestDeLactato(
        atleta_id=data.swimmer_id, fecha=data.test_date,
        modo=ModoDeLactato.desde_texto(data.mode), zona=Zona.desde_texto(data.target_zone),
        distancia_rep=data.rep_distance,
        descanso=TipoDeDescanso.desde_texto(data.rest_type) if data.rest_type else None,
        descanso_s=data.rest_s,
        propuesto=(data.proposed_min, data.proposed_max) if data.proposed_min is not None else None,
        referencia=data.reference_time, tramo_m=data.counted_segment_m,
        protocolo=ProtocoloDeMuestra(
            sitio=SitioDeMuestra.desde_texto(data.sample_site) if data.sample_site else None,
            analizador=(data.analyzer or "").strip() or None,
            minuto=data.sample_minute,
            metodo_fc=MetodoDeFc.desde_texto(data.hr_method) if data.hr_method else None,
        ),
        notas=(data.notes or "").strip() or None,
        repeticiones=[
            Repeticion(
                i + 1, Tiempo(r.swim_time), lactato=r.lactate, fc=r.heart_rate,
                esfuerzo=r.effort, brazadas=tuple(r.stroke_counts),
                tiempo_tramo=Tiempo(r.segment_time) if r.segment_time else None,
            )
            for i, r in enumerate(data.reps)
        ],
    )


def analizar(test: TestDeLactato) -> LactateAnalysis:
    reps = []
    for r in test.repeticiones:
        frecuencia, estimada = test.frecuencia_de_ciclo(r)
        zona = test.estado_de_zona(r.lactato) if r.lactato is not None else None
        reps.append(LactateRepOut(
            rep_number=r.numero, swim_time=r.tiempo.segundos, lactate=r.lactato,
            heart_rate=r.fc, effort=r.esfuerzo, stroke_counts=list(r.brazadas),
            segment_time=r.tiempo_tramo.segundos if r.tiempo_tramo else None,
            speed=round(test.velocidad(r), 3),
            pct_proposed=_r(test.pct_del_propuesto(r), 1),
            pct_reference=_r(test.pct_de_referencia(r), 1),
            strokes_mean=_r(r.brazadas_medias()),
            m_per_stroke=_r(test.metros_por_brazada(r)),
            cycle_rate=_r(frecuencia, 1), cycle_rate_estimated=estimada,
            stroke_index=_r(test.indice_de_brazada(r)),
            internal_drift_pct=_r(r.deriva_interna_pct(), 1),
            lactate_zone=zona.value if zona else None,
        ))

    valores = [v for _, v in test.muestras()]
    mediana = test.lactato_mediano()
    zona_mediana = test.estado_de_zona(mediana) if mediana is not None else None
    con_conteo = test.con_conteo()
    resumen = LactateSummary(
        mean_time=round(test.tiempo_medio().segundos, 2),
        cv_pct=round(test.cv_pct(), 2), slope=round(test.pendiente(), 3),
        speed=round(test.velocidad(), 3),
        pct_proposed=_r(test.pct_del_propuesto(), 1),
        diff_proposed=_r(test.diferencia_con_propuesto(), 1),
        pct_reference=_r(test.pct_de_referencia(), 1),
        lactate_median=_r(mediana), lactate_min=min(valores) if valores else None,
        lactate_max=max(valores) if valores else None,
        lactate_zone=zona_mediana.value if zona_mediana else None,
        steady_state=test.estado_estable(), second_half_rise=test.subida_en_la_segunda_mitad(),
        strokes_first=_r(con_conteo[0].brazadas_medias()) if con_conteo else None,
        strokes_last=_r(con_conteo[-1].brazadas_medias()) if con_conteo else None,
        stroke_drift_pct=_r(test.deriva_de_brazada_pct(), 1),
        stroke_index=_r(test.indice_de_brazada()),
    )
    return LactateAnalysis(
        zone_range=test.zona.rango_de_lactato, reps=reps, summary=resumen,
        warnings=[
            LactateWarning(rep_number=a.repeticion, field=a.campo, message=a.mensaje)
            for a in avisos(test)
        ],
    )


def to_response(fila: LactateTest) -> LactateTestResponse:
    analisis = analizar(test_de_lactato_desde_fila(fila))
    return LactateTestResponse(
        **analisis.model_dump(),
        id=fila.id, swimmer_id=fila.swimmer_id, test_date=fila.test_date, mode=fila.mode,
        target_zone=fila.target_zone, rep_distance=fila.rep_distance,
        rest_type=fila.rest_type, rest_s=fila.rest_s,
        proposed_min=fila.proposed_min, proposed_max=fila.proposed_max,
        reference_time=fila.reference_time, counted_segment_m=fila.counted_segment_m,
        sample_site=fila.sample_site, analyzer=fila.analyzer,
        sample_minute=fila.sample_minute, hr_method=fila.hr_method,
        notes=fila.notes, is_active=fila.is_active,
    )


async def crear(
    repo: RepositorioDeTestsDeLactato, atletas: RepositorioDeAtletas,
    data: LactateTestCreate, principal: Principal,
) -> LactateTest | None:
    """`None` si el nadador no es visible para quien escribe (el router: 404)."""
    if await atletas.por_id(data.swimmer_id) is None:
        return None
    test = entidad_desde_peticion(data)
    return await repo.guardar(fila_de_test_de_lactato(test, team_id=principal.team_id))
