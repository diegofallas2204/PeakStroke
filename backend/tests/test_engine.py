"""Tests del motor de cálculo (funciones puras)."""
from datetime import date

import pytest

from app.engine.aerobic import analyze_splits, css_from_400_50
from app.engine.curves import CURVES, curve_progress
from app.engine.feasibility import analyze_feasibility
from app.engine.km_distribution import distribute_km
from app.engine.progression import (
    WeekEntry, generate_plan, performance_status, recalculate_remaining,
)
from app.engine.time_utils import to_clock, to_seconds
from app.engine.zones import calc_zones


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
        assert all(b >= a for a, b in zip(values, values[1:]))


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
        assert result.status == "ok" and result.tier == 2
        assert "level" in result.detail

    def test_aggressive_goal_recommends_weeks(self):
        result = analyze_feasibility(100, "libre", 60.0, 52.0, 12, 4)
        assert result.status == "aggressive"
        assert result.recommended_weeks and result.recommended_weeks > 12

    def test_tier1_label_for_long_distance(self):
        result = analyze_feasibility(800, "libre", 570.0, 552.0, 12, 4)
        assert result.tier == 1
        assert "level" in result.detail

    def test_goal_already_met(self):
        result = analyze_feasibility(100, "libre", 55.0, 56.0, 12, 4)
        assert result.status == "ok" and result.improvement_per_micro == 0.0

    def test_second_macro_higher_ceiling(self):
        r1 = analyze_feasibility(800, "libre", 570.0, 540.0, 12, 4, n_mac=1)
        r2 = analyze_feasibility(800, "libre", 570.0, 540.0, 12, 4, n_mac=2)
        assert r2.realistic_ceiling > r1.realistic_ceiling

    def test_n_mac_default_equals_1(self):
        r_def = analyze_feasibility(800, "libre", 570.0, 540.0, 12, 4)
        r1    = analyze_feasibility(800, "libre", 570.0, 540.0, 12, 4, n_mac=1)
        assert r_def.realistic_ceiling == pytest.approx(r1.realistic_ceiling)

    def test_youth_age_better_ceiling(self):
        adult = analyze_feasibility(100, "libre", 60.0, 57.0, 12, 4, age=25)
        youth = analyze_feasibility(100, "libre", 60.0, 57.0, 12, 4, age=15)
        assert youth.realistic_ceiling < adult.realistic_ceiling

    def test_age_18_no_correction(self):
        r18 = analyze_feasibility(100, "libre", 60.0, 57.0, 12, 4, age=18)
        r25 = analyze_feasibility(100, "libre", 60.0, 57.0, 12, 4, age=25)
        assert r18.realistic_ceiling == pytest.approx(r25.realistic_ceiling)


class TestProgression:
    def test_generates_all_weeks_with_real_dates(self):
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "sigmoid", date(2026, 4, 27), 4)
        assert len(weeks) == 12
        assert weeks[0].week_date == date(2026, 4, 27)
        assert weeks[1].week_date == date(2026, 5, 4)
        assert all(w.week_date.weekday() == 0 for w in weeks)

    def test_reaches_goal(self):
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "linear", date(2026, 4, 27), 4)
        assert weeks[-1].expected_time == pytest.approx(64.5, abs=0.01)

    def test_monotonic_improvement(self):
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "sigmoid", date(2026, 4, 27), 4)
        times = [w.expected_time for w in weeks]
        assert all(b <= a for a, b in zip(times, times[1:]))

    def test_recalculate_anchors_on_real(self):
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "sigmoid", date(2026, 4, 27), 4)
        recalculate_remaining(weeks, from_week=7, anchor_time=66.9,
                              goal_time=64.5, curve="sigmoid", distance=100)
        assert weeks[-1].expected_time == pytest.approx(64.5, abs=0.01)
        assert weeks[6].expected_time < 66.9

    def test_disabled_weeks_do_not_progress(self):
        weeks = generate_plan(100, 67.8, 64.5, 12, 320, "sigmoid", date(2026, 4, 27), 4)
        recalculate_remaining(weeks, from_week=5, anchor_time=66.5, goal_time=64.5,
                              curve="linear", distance=100, disabled_weeks={6, 7})
        w6 = next(w for w in weeks if w.week_number == 6)
        w5 = next(w for w in weeks if w.week_number == 5)
        assert w6.disabled and w6.expected_time == pytest.approx(w5.expected_time)
        assert weeks[-1].expected_time == pytest.approx(64.5, abs=0.01)

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
