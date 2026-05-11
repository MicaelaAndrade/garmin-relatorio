"""Comparação mês corrente vs mesmo mês ano passado."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from ..db import connect


SPORT_LABEL = {
    "run": "Corrida",
    "bike": "Bike",
    "swim": "Nado",
    "strength": "Força",
    "yoga": "Yoga",
    "walking": "Caminhada",
}


def year_over_year() -> dict[str, Any]:
    today = date.today()
    # Mês corrente: dia 1 até hoje
    month_start = today.replace(day=1)
    # Mesmo período no ano passado
    try:
        last_year_start = month_start.replace(year=month_start.year - 1)
        last_year_end = today.replace(year=today.year - 1)
    except ValueError:
        # fallback pra 29/02 -> 28/02
        last_year_start = date(month_start.year - 1, month_start.month, 1)
        last_year_end = date(today.year - 1, today.month, min(today.day, 28))

    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT sport, started_at, distance_m, duration_s, calories, avg_pace_s_km, avg_hr
            FROM activities
            """,
            conn,
        )

    if df.empty:
        return {"available": False}
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["d"] = df["started_at"].dt.date

    def _agg(filtered: pd.DataFrame) -> dict[str, Any]:
        if filtered.empty:
            return {"sessions": 0, "duration_min": 0, "distance_km": 0, "kcal": 0, "by_sport": {}}
        by_sport: dict[str, dict] = {}
        for sport, sub in filtered.groupby("sport"):
            avg_pace = (
                float(sub["avg_pace_s_km"].dropna().mean())
                if sub["avg_pace_s_km"].notna().any()
                else None
            )
            avg_hr = float(sub["avg_hr"].dropna().mean()) if sub["avg_hr"].notna().any() else None
            by_sport[sport] = {
                "sessions": int(len(sub)),
                "duration_min": round(float(sub["duration_s"].sum() / 60), 1),
                "distance_km": round(float(sub["distance_m"].fillna(0).sum() / 1000), 2),
                "kcal": int(sub["calories"].fillna(0).sum()),
                "avg_pace_s_km": round(avg_pace, 0) if avg_pace else None,
                "avg_hr": round(avg_hr, 0) if avg_hr else None,
            }
        return {
            "sessions": int(len(filtered)),
            "duration_min": round(float(filtered["duration_s"].sum() / 60), 1),
            "distance_km": round(float(filtered["distance_m"].fillna(0).sum() / 1000), 2),
            "kcal": int(filtered["calories"].fillna(0).sum()),
            "by_sport": by_sport,
        }

    this_period = df[(df["d"] >= month_start) & (df["d"] <= today)]
    last_period = df[(df["d"] >= last_year_start) & (df["d"] <= last_year_end)]
    this_agg = _agg(this_period)
    last_agg = _agg(last_period)

    def _pct_delta(now: float, then: float) -> float | None:
        if not then:
            return None
        return round((now - then) / then * 100, 1)

    deltas = {
        "sessions": this_agg["sessions"] - last_agg["sessions"],
        "duration_min": round(this_agg["duration_min"] - last_agg["duration_min"], 1),
        "distance_km": round(this_agg["distance_km"] - last_agg["distance_km"], 2),
        "kcal": this_agg["kcal"] - last_agg["kcal"],
        "sessions_pct": _pct_delta(this_agg["sessions"], last_agg["sessions"]),
        "distance_pct": _pct_delta(this_agg["distance_km"], last_agg["distance_km"]),
    }

    # Por modalidade — alinhado
    sport_rows = []
    all_sports = sorted(set(list(this_agg["by_sport"].keys()) + list(last_agg["by_sport"].keys())))
    for sport in all_sports:
        now = this_agg["by_sport"].get(sport, {"sessions": 0, "distance_km": 0, "duration_min": 0, "avg_pace_s_km": None})
        then = last_agg["by_sport"].get(sport, {"sessions": 0, "distance_km": 0, "duration_min": 0, "avg_pace_s_km": None})
        pace_delta = None
        if now.get("avg_pace_s_km") and then.get("avg_pace_s_km"):
            pace_delta = round(now["avg_pace_s_km"] - then["avg_pace_s_km"], 0)
        sport_rows.append({
            "sport": sport,
            "label": SPORT_LABEL.get(sport, sport),
            "this_sessions": now.get("sessions", 0),
            "last_sessions": then.get("sessions", 0),
            "this_distance_km": now.get("distance_km", 0),
            "last_distance_km": then.get("distance_km", 0),
            "this_duration_min": now.get("duration_min", 0),
            "last_duration_min": then.get("duration_min", 0),
            "this_pace_s_km": now.get("avg_pace_s_km"),
            "last_pace_s_km": then.get("avg_pace_s_km"),
            "pace_delta_s": pace_delta,
        })

    return {
        "available": True,
        "this_period": {
            "start": month_start.isoformat(),
            "end": today.isoformat(),
            "label": today.strftime("%b/%Y"),
            **this_agg,
        },
        "last_period": {
            "start": last_year_start.isoformat(),
            "end": last_year_end.isoformat(),
            "label": last_year_end.strftime("%b/%Y"),
            **last_agg,
        },
        "deltas": deltas,
        "by_sport_compare": sport_rows,
    }
