"""Tests directos del motor de dominio (ScienceEngine).

Cubre: funcionalidad base existente (verde) + características nuevas (rojo):
  - Degradación por macrociclo: I_max × 0.85^(n_mac-1)   §4.3
  - Corrección para menores de 18 años                     §4.4
"""
from datetime import date

import pytest

from app.domain.engine import (
    F_FASE,
    I_MAX_TABLE,
    STROKE_TPACE_CORRECTION_S,
    ScienceEngine,
    allowed_strokes,
    classify_level,
    confidence_margin,
    profile_for_event,
    race_pace_100,
)


# ─────────────────────────────────────────────────────────────────────────────
# Funciones puras de apoyo
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifyLevel:
    def test_beginner(self):
        assert classify_level(155.0) == "beginner"

    def test_recreational(self):
        assert classify_level(130.0) == "recreational"

    def test_advanced(self):
        assert classify_level(110.0) == "advanced"

    def test_competitive(self):
        assert classify_level(80.0) == "competitive"

    def test_elite(self):
        assert classify_level(60.0) == "elite"

    def test_boundary_competitive(self):
        # 70.0 es el límite entre competitive y elite (> 70 = competitive)
        assert classify_level(70.1) == "competitive"
        assert classify_level(70.0) == "elite"


class TestProfileForEvent:
    def test_sprint_velocity(self):
        assert profile_for_event(50) == "velocidad"
        assert profile_for_event(100) == "velocidad"

    def test_middle_distance(self):
        assert profile_for_event(200) == "medio fondo"
        assert profile_for_event(400) == "medio fondo"

    def test_long_distance(self):
        assert profile_for_event(800) == "fondo"
        assert profile_for_event(1500) == "fondo"


class TestConfidenceMargin:
    def test_early_weeks_high_precision(self):
        assert confidence_margin(1) == 2
        assert confidence_margin(4) == 2

    def test_mid_weeks(self):
        assert confidence_margin(5) == 4
        assert confidence_margin(8) == 4

    def test_late_weeks_lower_precision(self):
        assert confidence_margin(13) == 8


class TestRacePace100:
    def test_long_event_no_correction(self):
        assert race_pace_100(240.0, 200) == pytest.approx(120.0)

    def test_1500m_no_correction(self):
        assert race_pace_100(900.0, 1500) == pytest.approx(60.0)

    def test_sprint_fatigue_correction(self):
        raw = race_pace_100(25.0, 50)
        assert raw == pytest.approx(25.0 / 0.5 * 1.100)


class TestIMaxTable:
    def test_all_levels_present(self):
        for level in ("beginner", "recreational", "advanced", "competitive", "elite"):
            assert level in I_MAX_TABLE

    def test_all_standard_events_present(self):
        for event in (50, 100, 200, 400, 800, 1500):
            assert event in I_MAX_TABLE["competitive"]

    def test_longer_event_higher_imax_same_level(self):
        for level in I_MAX_TABLE:
            assert I_MAX_TABLE[level][1500] > I_MAX_TABLE[level][50]

    def test_higher_level_lower_imax_same_event(self):
        for event in (100, 400, 800):
            assert I_MAX_TABLE["beginner"][event] > I_MAX_TABLE["elite"][event]

    def test_values_in_range(self):
        for level, events in I_MAX_TABLE.items():
            for event, val in events.items():
                assert 0 < val < 0.10, f"{level}/{event}: {val} fuera de [0,0.10]"


class TestFFase:
    def test_taper_is_peak(self):
        assert F_FASE["taper"] == max(F_FASE.values())

    def test_base_general_is_lowest(self):
        assert F_FASE["base_general"] == min(F_FASE.values())

    def test_all_macro_phases_present(self):
        for phase in ("base_general", "base_especifica", "umbral_css", "pre_competitivo", "taper"):
            assert phase in F_FASE

    def test_ascending_order(self):
        ordered = [F_FASE[p] for p in
                   ("base_general", "base_especifica", "umbral_css", "pre_competitivo", "taper")]
        assert ordered == sorted(ordered)


class TestAllowedStrokes:
    def test_800_1500_only_libre(self):
        assert allowed_strokes(800) == ["libre"]
        assert allowed_strokes(1500) == ["libre"]

    def test_400_libre_and_combinado_only(self):
        strokes = allowed_strokes(400)
        assert "libre" in strokes
        assert "combinado" in strokes
        assert "mariposa" not in strokes

    def test_100_all_strokes(self):
        strokes = allowed_strokes(100)
        assert len(strokes) == 5


# ─────────────────────────────────────────────────────────────────────────────
# ScienceEngine — funcionalidad base (deben PASAR)
# ─────────────────────────────────────────────────────────────────────────────

class TestScienceEngineBasics:

    def test_plan_returns_plan_result(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=236.0,
            distance=200, stroke="libre", pool="50",
        )
        assert result.distance == 200
        assert result.level in ("beginner", "recreational", "advanced", "competitive", "elite")
        assert result.feas_status in ("ok", "warning", "aggressive")

    def test_standard_macro_up_to_15_weeks(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=239.0,
            distance=200, stroke="libre", pool="50",
        )
        assert result.macro_weeks <= 15
        assert len(result.weeks) >= 1

    def test_zone_hierarchy_r1_slowest(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=236.0,
            distance=200, stroke="libre", pool="50",
        )
        paces = result.weeks[0].zones.paces
        assert paces["R1"] > paces["R2"] > paces["MVO2"] > paces["RL"] > paces["V"]

    def test_predicted_time_improves_over_weeks(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=234.0,
            distance=200, stroke="libre", pool="50",
        )
        times = [w.predicted_time for w in result.weeks if not w.is_extension]
        assert times[-1] < times[0]

    def test_feasibility_ok_for_small_goal(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=239.0,
            distance=200, stroke="libre", pool="50",
        )
        assert result.feas_status == "ok"

    def test_feasibility_aggressive_for_huge_goal(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=180.0,
            distance=200, stroke="libre", pool="50",
        )
        assert result.feas_status == "aggressive"

    def test_extension_weeks_added_when_aggressive(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=180.0,
            distance=200, stroke="libre", pool="50",
        )
        assert len(result.weeks) > 15

    def test_butterfly_zones_slower_than_freestyle(self):
        eng = ScienceEngine()
        libre = eng.generate_plan(current_time=120.0, goal_time=118.0,
                                  distance=100, stroke="libre", pool="50")
        mariposa = eng.generate_plan(current_time=120.0, goal_time=118.0,
                                     distance=100, stroke="mariposa", pool="50")
        assert mariposa.weeks[0].zones.paces["R1"] > libre.weeks[0].zones.paces["R1"]

    def test_pool_25m_zones_faster_than_50m(self):
        eng = ScienceEngine()
        lcm = eng.generate_plan(current_time=240.0, goal_time=236.0,
                                distance=200, stroke="libre", pool="50")
        scm = eng.generate_plan(current_time=240.0, goal_time=236.0,
                                distance=200, stroke="libre", pool="25")
        assert scm.weeks[0].zones.paces["R1"] < lcm.weeks[0].zones.paces["R1"]

    def test_realistic_final_less_than_current(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=230.0,
            distance=200, stroke="libre", pool="50",
        )
        assert result.realistic_final < result.current_time

    def test_week_one_starts_from_current(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=235.0,
            distance=200, stroke="libre", pool="50",
            start_date=date(2026, 1, 5),
        )
        assert result.weeks[0].week == 1
        assert result.weeks[0].week_date == date(2026, 1, 5)

    def test_planned_km_positive_all_weeks(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=235.0,
            distance=200, stroke="libre", pool="50",
        )
        assert all(w.planned_km > 0 for w in result.weeks)

    def test_extension_phase_label(self):
        result = ScienceEngine().generate_plan(
            current_time=240.0, goal_time=180.0,
            distance=200, stroke="libre", pool="50",
        )
        ext_weeks = [w for w in result.weeks if w.is_extension]
        assert ext_weeks, "No hay semanas de extensión en un plan agresivo"

    def test_stroke_correction_values_positive(self):
        for stroke, corr in STROKE_TPACE_CORRECTION_S.items():
            if stroke != "freestyle":
                assert corr > 0, f"{stroke} debería tener corrección positiva"


# ─────────────────────────────────────────────────────────────────────────────
# DEGRADACIÓN POR MACROCICLO — RED (fallan hasta implementar)
# ─────────────────────────────────────────────────────────────────────────────

class TestMacrocycleDegradation:
    """I_max^(n_mac) = I_max × 0.85^(n_mac-1)   §4.3"""

    def test_second_macro_less_improvement_than_first(self):
        eng = ScienceEngine()
        mac1 = eng.generate_plan(current_time=300.0, goal_time=260.0,
                                 distance=800, stroke="libre", pool="50", n_mac=1)
        mac2 = eng.generate_plan(current_time=300.0, goal_time=260.0,
                                 distance=800, stroke="libre", pool="50", n_mac=2)
        improvement_mac1 = mac1.current_time - mac1.realistic_final
        improvement_mac2 = mac2.current_time - mac2.realistic_final
        assert improvement_mac2 < improvement_mac1

    def test_n_mac_1_equals_default(self):
        eng = ScienceEngine()
        default = eng.generate_plan(current_time=240.0, goal_time=235.0,
                                    distance=400, stroke="libre", pool="50")
        explicit1 = eng.generate_plan(current_time=240.0, goal_time=235.0,
                                      distance=400, stroke="libre", pool="50", n_mac=1)
        assert default.realistic_final == pytest.approx(explicit1.realistic_final)

    def test_degradation_ratio_approximately_085(self):
        eng = ScienceEngine()
        mac1 = eng.generate_plan(current_time=300.0, goal_time=250.0,
                                 distance=800, stroke="libre", pool="50", n_mac=1)
        mac2 = eng.generate_plan(current_time=300.0, goal_time=250.0,
                                 distance=800, stroke="libre", pool="50", n_mac=2)
        improvement_mac1 = mac1.current_time - mac1.realistic_final
        improvement_mac2 = mac2.current_time - mac2.realistic_final
        assert improvement_mac2 / improvement_mac1 == pytest.approx(0.85, abs=0.01)

    def test_third_macro_factor_0_7225(self):
        eng = ScienceEngine()
        mac1 = eng.generate_plan(current_time=300.0, goal_time=250.0,
                                 distance=800, stroke="libre", pool="50", n_mac=1)
        mac3 = eng.generate_plan(current_time=300.0, goal_time=250.0,
                                 distance=800, stroke="libre", pool="50", n_mac=3)
        improvement_mac1 = mac1.current_time - mac1.realistic_final
        improvement_mac3 = mac3.current_time - mac3.realistic_final
        assert improvement_mac3 / improvement_mac1 == pytest.approx(0.85 ** 2, abs=0.01)

    def test_feasibility_degrades_with_later_macro(self):
        eng = ScienceEngine()
        mac1 = eng.generate_plan(current_time=240.0, goal_time=234.0,
                                 distance=400, stroke="libre", pool="50", n_mac=1)
        mac4 = eng.generate_plan(current_time=240.0, goal_time=234.0,
                                 distance=400, stroke="libre", pool="50", n_mac=4)
        statuses = {"ok": 0, "warning": 1, "aggressive": 2}
        assert statuses[mac4.feas_status] >= statuses[mac1.feas_status]


# ─────────────────────────────────────────────────────────────────────────────
# CORRECCIÓN PARA MENORES — RED (fallan hasta implementar)
# ─────────────────────────────────────────────────────────────────────────────

class TestYouthCorrection:
    """Atletas < 18 años tienen I_max × 1.5-2.0 vs adulto.   §4.4"""

    def test_youth_realistic_ceiling_better_than_adult(self):
        eng = ScienceEngine()
        adult = eng.generate_plan(current_time=60.0, goal_time=58.0,
                                  distance=100, stroke="libre", pool="50", age=25)
        youth = eng.generate_plan(current_time=60.0, goal_time=58.0,
                                  distance=100, stroke="libre", pool="50", age=15)
        assert youth.realistic_final < adult.realistic_final

    def test_no_age_equals_adult(self):
        eng = ScienceEngine()
        no_age = eng.generate_plan(current_time=60.0, goal_time=58.0,
                                   distance=100, stroke="libre", pool="50")
        adult = eng.generate_plan(current_time=60.0, goal_time=58.0,
                                  distance=100, stroke="libre", pool="50", age=25)
        assert no_age.realistic_final == pytest.approx(adult.realistic_final)

    def test_age_18_no_youth_correction(self):
        eng = ScienceEngine()
        age18 = eng.generate_plan(current_time=60.0, goal_time=58.0,
                                  distance=100, stroke="libre", pool="50", age=18)
        age25 = eng.generate_plan(current_time=60.0, goal_time=58.0,
                                  distance=100, stroke="libre", pool="50", age=25)
        assert age18.realistic_final == pytest.approx(age25.realistic_final)

    def test_youth_improvement_at_least_50_percent_more(self):
        eng = ScienceEngine()
        adult = eng.generate_plan(current_time=300.0, goal_time=260.0,
                                  distance=800, stroke="libre", pool="50", age=25)
        youth = eng.generate_plan(current_time=300.0, goal_time=260.0,
                                  distance=800, stroke="libre", pool="50", age=14)
        imp_adult = adult.current_time - adult.realistic_final
        imp_youth = youth.current_time - youth.realistic_final
        assert imp_youth >= imp_adult * 1.4
