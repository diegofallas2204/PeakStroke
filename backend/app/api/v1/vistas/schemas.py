"""Schemas del dashboard y la tabla del equipo."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class TeamWeekPoint(BaseModel):
    week_number: int
    date_label: str
    expected_progress: float          # % de mejora planificada acumulada (promedio equipo)
    real_progress: float | None       # % de mejora real acumulada (solo semanas con datos)
    is_current: bool = False


class AthleteStatusRow(BaseModel):
    athlete_plan_id: int
    swimmer_id: int
    event_id: int
    name: str
    specialty: str
    event_label: str
    expected_time: float
    recalc_time: float | None
    real_time: float | None
    status: str | None                # ahead | on_track | behind | pending
    diff_seconds: float | None
    goal_time: float
    current_time: float
    progress_percent: float           # % del objetivo ya logrado (según último real)


class PhaseStrip(BaseModel):
    name: str
    type: str
    color: str
    week_start: int
    week_end: int
    is_current: bool


class CompetitionInfo(BaseModel):
    name: str
    week_number: int
    week_date: date
    days: int
    is_main: bool
    weeks_away: int | None


class DashboardSummary(BaseModel):
    plan_id: int
    plan_name: str
    plan_status: str = "active"       # estado efectivo: active|finished|draft|suspended
    start_date: date
    total_weeks: int
    current_week: int | None
    current_phase: str | None
    athletes_total: int
    events_total: int
    ahead: int
    on_track: int
    behind: int
    pending: int
    compliance_percent: float         # % de semanas pasadas con tiempo real registrado
    avg_deviation_percent: float | None
    progression: list[TeamWeekPoint]
    statuses: list[AthleteStatusRow]
    phases: list[PhaseStrip]
    competitions: list[CompetitionInfo]


class TeamWeekZones(BaseModel):
    event_id: int
    week_id: int | None
    name: str
    specialty: str
    event_label: str
    expected_time: float | None
    pace_100m: float | None
    real_time: float | None
    status: str | None
    zones: dict | None
    zone_km: dict | None
    planned_km: float | None
    disabled: bool = False


class TeamWeekResponse(BaseModel):
    week_number: int
    date_label: str
    phase: str | None
    rows: list[TeamWeekZones]
