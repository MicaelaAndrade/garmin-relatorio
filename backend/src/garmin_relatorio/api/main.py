"""FastAPI servindo o dashboard."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..analysis import (
    acwr,
    activities,
    coach,
    comparisons,
    cycle,
    garmin_metrics,
    overtraining,
    pace_evolution,
    performance,
    personal_records,
    races as races_analysis,
    recovery,
    strength,
    training_plan,
    volume,
    weekly_summary,
    zones_distribution,
)
from ..db import init_db

app = FastAPI(title="garmin-relatorio", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard() -> dict:
    """Endpoint principal: tudo o que o frontend precisa em uma chamada."""
    return {
        "current_week": volume.latest_week_totals(),
        "weekly_volume": volume.weekly_summary(days=84),
        "injury_risk": acwr.current_status(),
        "acwr_series": acwr.acwr_series(days=60),
        "readiness": recovery.readiness_today(),
        "sleep": recovery.sleep_series(days=30),
        "daily_metrics": recovery.daily_metrics_series(days=30),
        "predictions": {
            "run": performance.predict_race("run"),
            "swim": performance.predict_race("swim"),
            "bike": performance.predict_race("bike"),
        },
        "garmin_predictions": garmin_metrics.garmin_race_predictions(),
        "garmin_predictions_series": garmin_metrics.garmin_predictions_series(180),
        "vo2max": {
            "latest": garmin_metrics.latest_vo2max(),
            "series": garmin_metrics.vo2max_series(365, "run"),
        },
        "recent_activities": activities.recent_activities(120),
        "calendar": activities.daily_load_calendar(180),
        "overtraining": overtraining.overtraining_score(),
        "personal_records": personal_records.list_prs(),
        "race_comparison": comparisons.riegel_vs_garmin(),
        "zones_by_sport": {
            sport: {
                "weekly": zones_distribution.weekly_zone_distribution(84, sport=sport),
                "polarization": zones_distribution.polarization_index(28, sport=sport),
            }
            for sport in ("run", "bike", "swim")
        },
        "zones_weekly": zones_distribution.weekly_zone_distribution(84),
        "polarization": zones_distribution.polarization_index(28),
        "pace_evolution": pace_evolution.monthly_pace_evolution(365),
        "training_plan": training_plan.weekly_plan(),
        "coach_schedule": coach.coach_schedule(),
        "coach_today": coach.coach_today(),
        "strength": strength.strength_dashboard(),
        "ai_available": bool(__import__("os").getenv("ANTHROPIC_API_KEY", "").strip()),
    }


@app.get("/api/volume")
def get_volume(days: int = 90) -> dict:
    return {"weekly": volume.weekly_summary(days), "current": volume.latest_week_totals()}


@app.get("/api/injury-risk")
def get_injury_risk(days: int = 60) -> dict:
    return {"current": acwr.current_status(), "series": acwr.acwr_series(days)}


@app.get("/api/recovery")
def get_recovery(days: int = 30) -> dict:
    return {
        "sleep": recovery.sleep_series(days),
        "daily": recovery.daily_metrics_series(days),
        "readiness": recovery.readiness_today(),
    }


@app.get("/api/performance/{sport}")
def get_performance(sport: str) -> dict:
    return performance.predict_race(sport)


@app.get("/api/vo2max")
def get_vo2max(days: int = 365, sport: str = "run") -> dict:
    return {
        "latest": garmin_metrics.latest_vo2max(),
        "series": garmin_metrics.vo2max_series(days, sport),
    }


@app.get("/api/garmin-predictions")
def get_garmin_predictions(days: int = 180) -> dict:
    return {
        "current": garmin_metrics.garmin_race_predictions(),
        "series": garmin_metrics.garmin_predictions_series(days),
    }


@app.get("/api/recent-activities")
def get_recent_activities(limit: int = 20) -> list[dict]:
    return activities.recent_activities(limit)


@app.get("/api/calendar")
def get_calendar(days: int = 180) -> list[dict]:
    return activities.daily_load_calendar(days)


@app.get("/api/overtraining")
def get_overtraining() -> dict:
    return overtraining.overtraining_score()


@app.get("/api/personal-records")
def get_prs() -> list[dict]:
    return personal_records.list_prs()


@app.get("/api/race-comparison")
def get_race_comparison() -> dict:
    return comparisons.riegel_vs_garmin()


@app.get("/api/zones")
def get_zones(days: int = 84) -> dict:
    return {
        "weekly": zones_distribution.weekly_zone_distribution(days),
        "polarization": zones_distribution.polarization_index(min(days, 28)),
    }


@app.get("/api/pace-evolution")
def get_pace_evolution(days: int = 365) -> dict:
    return pace_evolution.monthly_pace_evolution(days)


@app.get("/api/weekly-summary")
def get_weekly_summary(week_offset: int = 0, use_ai: bool = True) -> dict:
    return weekly_summary.generate_summary(week_offset=week_offset, use_ai=use_ai)


@app.get("/api/races")
def get_races(include_past: bool = False) -> list[dict]:
    return races_analysis.list_races(include_past=include_past)


@app.get("/api/training-plan")
def get_training_plan() -> dict:
    return training_plan.weekly_plan()


@app.get("/api/coach-schedule")
def get_coach_schedule() -> dict:
    return coach.coach_schedule()


@app.get("/api/coach-today")
def get_coach_today() -> dict:
    return coach.coach_today()


@app.get("/api/strength")
def get_strength() -> dict:
    return strength.strength_dashboard()


@app.get("/api/strength/{routine_id}")
def get_strength_routine(routine_id: int) -> dict:
    r = strength.strength_routine(routine_id)
    if r is None:
        return {"error": "not_found"}
    return r


@app.get("/api/cycle")
def get_cycle() -> dict:
    return cycle.cycle_dashboard()
