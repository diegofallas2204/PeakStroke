"""Tests del motor de cálculo (funciones puras).

Desde el paso 4 del rediseño preguntan al **motor único**
(`app/dominio/servicios/`); los asserts no han cambiado, solo a quién se le
hacen. Lo que sigue viniendo de `app/engine/` es lo que C4 no absorbe: el
análisis del test aeróbico y la conversión de tiempos.
"""
from datetime import date

import pytest

from app.dominio.servicios.curvas import Curva
from app.dominio.servicios.envolvente import envolvente_de
from app.dominio.servicios.kilometraje import reparto_de_km
from app.dominio.servicios.motor import MOTOR
from app.engine.aerobic import analyze_splits, css_from_400_50
from app.engine.time_utils import to_clock, to_seconds

CURVES = [c.clave for c in Curva.catalogo()]


def curve_progress(x: float, curve: str) -> float:
    return Curva.desde_clave(curve).progreso(x)


def calc_zones(pace, distance, stroke="libre", pool="50"):
    return MOTOR.zonas(pace, distance, stroke, pool)


def distribute_km(total_weeks, total_km, weeks_per_micro=4):
    return reparto_de_km(total_weeks, total_km, weeks_per_micro)


def science_envelope(distance, current_time, total_weeks, n_mac=1, age=None):
    return envolvente_de(distance, current_time, total_weeks, n_mac=n_mac, edad=age)


def analyze_feasibility(distance, stroke, current, goal, weeks, per_micro=4, n_mac=1, age=None):
    return MOTOR.factibilidad(distance, current, goal, weeks, semanas_por_micro=per_micro,
                              n_mac=n_mac, edad=age)


def generate_plan(distance, current, goal, weeks, km, curve, start, per_micro=4):
    return MOTOR.generar_plan(distance, current, goal, weeks, km, curve, start,
                              semanas_por_micro=per_micro)


def recalculate_remaining(weeks, from_week, anchor_time, goal_time, curve, distance,
                          disabled_weeks=None):
    return MOTOR.recalcular_desde(weeks, from_week, anchor_time, goal_time, curve,
                                  distance, deshabilitadas=disabled_weeks)


performance_status = MOTOR.estado_de_rendimiento


class TestTimeUtils:
    def test_mmss_to_seconds(self):
        assert to_seconds("1:05.32") == pytest.approx(65.32)

    def test_plain_seconds(self):
        assert to_seconds("53.4") == pytest.approx(53.4)

    def test_comma_decimal(self):
        assert to_seconds("1:05,32") == pytest.approx(65.32)

    def test_roundtrip(self):
        assert to_clock(65.32) == "1:05.32"
        assert to_clock(53.4) == "53.40"


class TestCurves:
    @pytest.mark.parametrize("curve", CURVES)
    def test_normalized_bounds(self, curve):
        assert curve_progress(0.0, curve) == pytest.approx(0.0, abs=1e-9)
        assert curve_progress(1.0, curve) == pytest.approx(1.0, abs=1e-9)

    @pytest.mark.parametrize("curve", CURVES)
    def test_monotonic(self, curve):
        values = [curve_progress(x / 20, curve) for x in range(21)]
        assert all(b >= a for a, b in zip(values, values[1:], strict=False))


class TestZones:
    def test_hierarchy_r1_slowest(self):
        # Modelo del dominio (perfil×distancia): R1 el más lento, V el más rápido.
        zones = calc_zones(70.0, 100)
        assert zones["R1"]["mid"] > zones["R2"]["mid"] > zones["MVO2"]["mid"] > \
            zones["RL"]["mid"] > zones["V"]["mid"]

    def test_anchored_to_race_pace(self):
        # R1 de 100m libre = ritmo × factor velocidad/100 (1.419), ±1% en min/max.
        zones = calc_zones(70.0, 100)
        assert zones["R1"]["mid"] == pytest.approx(70.0 * 1.419, abs=0.05)
        assert zones["R1"]["min"] < zones["R1"]["mid"] < zones["R1"]["max"]

    def test_stroke_correction_slows_zones(self):
        # Espalda suma corrección s/100m → zonas más lentas que libre.
        libre = calc_zones(70.0, 100, "libre")
        espalda = calc_zones(70.0, 100, "espalda")
        assert espalda["R1"]["mid"] > libre["R1"]["mid"]

    def test_pool_25_is_faster(self):
        # Piscina de 25m: ritmo más rápido (factor < 1) que la de 50m.
        lcm = calc_zones(70.0, 200, "libre", "50")
        scm = calc_zones(70.0, 200, "libre", "25")
        assert scm["R1"]["mid"] < lcm["R1"]["mid"]

    def test_all_zones_present_for_long_distance(self):
        # El dominio prescribe todas las zonas en todas las distancias.
        zones = calc_zones(75.0, 1500)
        assert all(zones[z] is not None for z in ("R1", "R2", "MVO2", "RL", "V"))


class TestKmDistribution:
    def test_total_preserved(self):
        km = distribute_km(12, 320, 4)
        assert sum(km) == pytest.approx(320, abs=1.5)

    def test_deload_weeks_lower(self):
        km = distribute_km(12, 320, 4)
        # Semana 4 (descarga del micro 1) < semana 3 (pico del micro 1)
        assert km[3] < km[2]

    def test_final_week_is_taper(self):
        km = distribute_km(12, 320, 4)
        assert km[-1] < max(km) * 0.7


class TestFeasibility:
    def test_realistic_goal_ok(self):
        result = analyze_feasibility(100, "libre", 60.0, 59.8, 12, 4)
        assert result.estado == "ok" and result.tier == 2
        assert "level" in result.detalle

    def test_aggressive_goal_recommends_weeks(self):
        result = analyze_feasibility(100, "libre", 60.0, 52.0, 12, 4)
        assert result.estado == "aggressive"
        assert result.semanas_recomendadas and result.semanas_recomendadas > 12

    def test_tier1_label_for_long_distance(self):
        result = analyze_feasibility(800, "libre", 570.0, 552.0, 12, 4)
        assert result.tier == 1
        assert "level" in result.detalle

    def test_goal_already_met(self):
        result = analyze_feasibility(100, "libre", 55.0, 56.0, 12, 4)
        assert result.estado == "ok" and result.mejora_por_micro_s == 0.0

    def test_second_macro_higher_ceiling(self):
        r1 = analyze_feasibility(800, "libre", 570.0, 540.0, 12, 4, n_mac=1)
        r2 = analyze_feasibility(800, "libre", 570.0, 540.0, 12, 4, n_mac=2)
        assert r2.techo_realista > r1.techo_realista

    def test_n_mac_default_equals_1(self):
        r_def = analyze_feasibility(800, "libre", 570.0, 540.0, 12, 4)
        r1    = analyze_feasibility(800, "libre", 570.0, 540.0, 12, 4, n_mac=1)
        assert r_def.techo_realista == pytest.approx(r1.techo_realista)

    def test_youth_age_better_ceiling(self):
        adult = analyze_feasibility(100, "libre", 60.0, 57.0, 12, 4, age=25)
        youth = analyze_feasibility(100, "libre", 60.0, 57.0, 12, 4, age=15)
        assert youth.techo_realista < adult.techo_realista

    def test_age_18_no_correction(self):
        r18 = analyze_feasibility(100, "libre", 60.0, 57.0, 12, 4, age=18)
        r25 = analyze_feasibility(100, "libre", 60.0, 57.0, 12, 4, age=25)
        assert r18.techo_realista == pytest.approx(r25.techo_realista)


class TestProgression:
    def test_generates_all_weeks_with_real_dates(self):
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "sigmoid", date(2026, 4, 27), 4)
        assert len(weeks) == 12
        assert weeks[0].fecha == date(2026, 4, 27)
        assert weeks[1].fecha == date(2026, 5, 4)
        assert all(w.fecha.weekday() == 0 for w in weeks)

    def test_reaches_feasible_goal(self):
        # Meta dentro del techo I_max: la curva la alcanza exactamente.
        weeks = generate_plan(100, 67.8, 67.3, 12, 320, "linear", date(2026, 4, 27), 4)
        assert weeks[-1].tiempo_esperado == pytest.approx(67.3, abs=0.02)

    def test_aggressive_goal_caps_at_realistic_ceiling(self):
        # Meta agresiva (supera el techo I_max): la curva NO llega a la meta, cierra
        # en el techo realista; la continuación va en la tabla de extensión.
        env = science_envelope(100, 67.8, 12)
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "linear", date(2026, 4, 27), 4)
        assert weeks[-1].tiempo_esperado == pytest.approx(env.techo_realista, abs=0.02)
        assert weeks[-1].tiempo_esperado > 64.5  # no alcanza la meta agresiva

    def test_no_week_exceeds_physiological_peak(self):
        # Ninguna curva mejora más rápido que el pico fisiológico (curva científica).
        env = science_envelope(100, 67.8, 12)
        for curve in CURVES:
            weeks = generate_plan(100, 67.8, 64.5, 12, 320, curve, date(2026, 4, 27), 4)
            steps = [weeks[i - 1].tiempo_esperado - weeks[i].tiempo_esperado for i in range(1, len(weeks))]
            # +0.01 de tolerancia por el redondeo a 2 decimales del tiempo esperado.
            assert max(steps) <= env.pico_semanal_s + 0.011, f"{curve} supera el pico"

    def test_science_curve_not_reshaped(self):
        # La curva científica define el envelope: el clamp es no-op para ella.
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "science", date(2026, 4, 27), 4)
        env = science_envelope(100, 67.8, 12)
        for i, w in enumerate(weeks):
            ideal = 67.8 - env.mejora_maxima_s * curve_progress((i + 1) / 12, "science")
            assert w.tiempo_esperado == pytest.approx(round(ideal, 2), abs=0.02)

    def test_curves_differ_in_shape(self):
        # Mismo techo, distinta forma: exp acelera al inicio, sigmoide en el centro.
        mid = 6
        exp = generate_plan(100, 67.8, 64.5, 12, 320, "exponential", date(2026, 4, 27), 4)
        sig = generate_plan(100, 67.8, 64.5, 12, 320, "sigmoid", date(2026, 4, 27), 4)
        assert exp[mid].tiempo_esperado != pytest.approx(sig[mid].tiempo_esperado, abs=0.05)
        # exponencial ya mejoró más a mitad de camino que la sigmoide
        assert exp[mid].tiempo_esperado < sig[mid].tiempo_esperado

    def test_monotonic_improvement(self):
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "sigmoid", date(2026, 4, 27), 4)
        times = [w.tiempo_esperado for w in weeks]
        assert all(b <= a for a, b in zip(times, times[1:], strict=False))

    def test_recalculate_anchors_on_real(self):
        # Recalcula desde el ancla real (66.9) sobre las 6 semanas restantes; queda
        # acotado por el techo I_max de ese tramo (meta agresiva → cierra en el techo).
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "sigmoid", date(2026, 4, 27), 4)
        recalculate_remaining(weeks, from_week=7, anchor_time=66.9,
                              goal_time=64.5, curve="sigmoid", distance=100)
        env = science_envelope(100, 66.9, 6)
        assert weeks[-1].tiempo_esperado == pytest.approx(env.techo_realista, abs=0.03)
        assert weeks[6].tiempo_esperado < 66.9

    def test_recalculate_reaches_feasible_goal(self):
        # Meta alcanzable desde el ancla: el recálculo sí la toca.
        weeks = generate_plan(100, 67.8, 67.4, 12, 320, "linear", date(2026, 4, 27), 4)
        recalculate_remaining(weeks, from_week=7, anchor_time=67.6,
                              goal_time=67.4, curve="linear", distance=100)
        assert weeks[-1].tiempo_esperado == pytest.approx(67.4, abs=0.03)

    def test_disabled_weeks_do_not_progress(self):
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "sigmoid", date(2026, 4, 27), 4)
        recalculate_remaining(weeks, from_week=5, anchor_time=66.5, goal_time=64.5,
                              curve="linear", distance=100, disabled_weeks={6, 7})
        w6 = next(w for w in weeks if w.numero == 6)
        w5 = next(w for w in weeks if w.numero == 5)
        assert w6.deshabilitada and w6.tiempo_esperado == pytest.approx(w5.tiempo_esperado)
        # 6 semanas activas restantes (5,8,9,10,11,12); cierra en su techo realista.
        env = science_envelope(100, 66.5, 6)
        assert weeks[-1].tiempo_esperado == pytest.approx(env.techo_realista, abs=0.05)

    def test_status_classification(self):
        assert performance_status(64.0, 65.0) == "ahead"
        assert performance_status(65.1, 65.0) == "on_track"
        assert performance_status(66.0, 65.0) == "behind"


class TestAerobic:
    def test_t30_average(self):
        analysis = analyze_splits([78.0] * 30, 100)
        assert analysis.avg_per100 == pytest.approx(78.0)
        assert analysis.trend == "stable"

    def test_custom_12x400_normalizes_per100(self):
        # 12×400 en 5:00 → parcial de 75.0 s/100m
        analysis = analyze_splits([300.0] * 12, 400)
        assert analysis.avg_per100 == pytest.approx(75.0)

    def test_declining_trend_detected(self):
        splits = [76.0 + i * 0.3 for i in range(15)]
        assert analyze_splits(splits, 100).trend == "declining"

    def test_css_wakayoshi(self):
        result = css_from_400_50(292.0, 27.9)
        assert result.css_ms == pytest.approx(350 / 264.1, abs=0.001)
        assert result.t_pace_100 == pytest.approx(100 / (350 / 264.1), abs=0.01)
