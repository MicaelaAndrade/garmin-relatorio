"""Stats anuais estilo Spotify Wrapped."""
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
    "other": "Outro",
}

WEEKDAY_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MONTHS_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def wrapped(year: int | None = None) -> dict[str, Any]:
    """Stats anuais. Default: ano corrente; passa year=2025 pra ano anterior."""
    target_year = year or date.today().year
    year_start = f"{target_year}-01-01"
    year_end = f"{target_year}-12-31"

    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT sport, started_at, duration_s, distance_m, calories, elevation_gain
            FROM activities
            WHERE started_at >= ? AND started_at <= ?
            """,
            conn,
            params=(year_start, year_end + "T23:59:59"),
        )
        daily_df = pd.read_sql_query(
            """
            SELECT date, total_kcal, active_kcal, steps
            FROM daily_metrics
            WHERE date >= ? AND date <= ?
            """,
            conn,
            params=(year_start, year_end),
        )

    if df.empty:
        return {"available": False, "year": target_year}

    df["started_at"] = pd.to_datetime(df["started_at"])
    df["date"] = df["started_at"].dt.date
    df["weekday"] = df["started_at"].dt.weekday
    df["month"] = df["started_at"].dt.month
    df["distance_km"] = df["distance_m"].fillna(0) / 1000
    df["duration_h"] = df["duration_s"] / 3600

    # === Totais gerais ===
    total_sessions = int(len(df))
    total_km = round(float(df["distance_km"].sum()), 1)
    total_hours = round(float(df["duration_h"].sum()), 1)
    total_kcal_activities = int(df["calories"].fillna(0).sum())
    total_elevation_m = int(df["elevation_gain"].fillna(0).sum())
    total_kcal_day = int(daily_df["total_kcal"].fillna(0).sum()) if not daily_df.empty else 0
    total_steps = int(daily_df["steps"].fillna(0).sum()) if not daily_df.empty else 0

    # === Por sport ===
    sport_stats = []
    by_sport = df.groupby("sport").agg(
        sessions=("sport", "count"),
        total_km=("distance_km", "sum"),
        total_hours=("duration_h", "sum"),
        total_kcal=("calories", "sum"),
    ).reset_index()
    by_sport = by_sport.sort_values("sessions", ascending=False)
    for row in by_sport.itertuples():
        sport_stats.append({
            "sport": row.sport,
            "label": SPORT_LABEL.get(row.sport, row.sport),
            "sessions": int(row.sessions),
            "total_km": round(float(row.total_km), 1),
            "total_hours": round(float(row.total_hours), 1),
            "total_kcal": int(row.total_kcal or 0),
            "pct_of_sessions": round(int(row.sessions) / total_sessions * 100, 1),
        })

    top_sport = sport_stats[0] if sport_stats else None

    # === Melhor mês (mais sessões) ===
    by_month = df.groupby("month").agg(
        sessions=("sport", "count"),
        total_km=("distance_km", "sum"),
        total_hours=("duration_h", "sum"),
    ).reset_index()
    best_month = None
    if not by_month.empty:
        top_m = by_month.sort_values("sessions", ascending=False).iloc[0]
        best_month = {
            "month": int(top_m["month"]),
            "label": MONTHS_PT[int(top_m["month"]) - 1],
            "sessions": int(top_m["sessions"]),
            "total_km": round(float(top_m["total_km"]), 1),
            "total_hours": round(float(top_m["total_hours"]), 1),
        }

    monthly_series = [
        {
            "month": int(m["month"]),
            "label": MONTHS_PT[int(m["month"]) - 1][:3],
            "sessions": int(m["sessions"]),
            "total_km": round(float(m["total_km"]), 1),
            "total_hours": round(float(m["total_hours"]), 1),
        }
        for m in by_month.sort_values("month").to_dict("records")
    ]

    # === Dia da semana favorito ===
    by_weekday = df.groupby("weekday").size().reset_index(name="sessions")
    fav_weekday = None
    if not by_weekday.empty:
        top_wd = by_weekday.sort_values("sessions", ascending=False).iloc[0]
        fav_weekday = {
            "weekday": int(top_wd["weekday"]),
            "label": WEEKDAY_PT[int(top_wd["weekday"])],
            "sessions": int(top_wd["sessions"]),
        }

    # === Streak mais longo (dias consecutivos com pelo menos 1 treino) ===
    unique_days = sorted(set(df["date"]))
    longest_streak = 0
    current_streak = 0
    streak_end_date = None
    streak_start_date = None
    if unique_days:
        prev = None
        for d in unique_days:
            if prev and (d - prev).days == 1:
                current_streak += 1
            else:
                current_streak = 1
            if current_streak > longest_streak:
                longest_streak = current_streak
                streak_end_date = d
                streak_start_date = unique_days[unique_days.index(d) - current_streak + 1]
            prev = d

    # === Maior treino (km) ===
    biggest_run = None
    if not df.empty:
        only_distance = df[df["distance_m"].fillna(0) > 0].sort_values("distance_km", ascending=False)
        if not only_distance.empty:
            top = only_distance.iloc[0]
            biggest_run = {
                "sport": top["sport"],
                "label": SPORT_LABEL.get(top["sport"], top["sport"]),
                "date": top["date"].isoformat(),
                "distance_km": round(float(top["distance_km"]), 2),
                "duration_h": round(float(top["duration_h"]), 1),
            }

    # === Treino mais longo (duração) ===
    longest_workout = None
    if not df.empty:
        top = df.sort_values("duration_s", ascending=False).iloc[0]
        longest_workout = {
            "sport": top["sport"],
            "label": SPORT_LABEL.get(top["sport"], top["sport"]),
            "date": top["date"].isoformat(),
            "duration_h": round(float(top["duration_h"]), 1),
            "distance_km": round(float(top["distance_km"]), 1),
        }

    active_days = len(unique_days)
    rest_days = 0
    if not df.empty:
        days_in_year = (
            min(date.today(), date(target_year, 12, 31)) - date(target_year, 1, 1)
        ).days + 1
        rest_days = days_in_year - active_days

    return {
        "available": True,
        "year": target_year,
        "totals": {
            "sessions": total_sessions,
            "km": total_km,
            "hours": total_hours,
            "kcal_activities": total_kcal_activities,
            "kcal_total_day": total_kcal_day,
            "elevation_m": total_elevation_m,
            "steps": total_steps,
            "active_days": active_days,
            "rest_days": rest_days,
        },
        "top_sport": top_sport,
        "sport_stats": sport_stats,
        "best_month": best_month,
        "monthly_series": monthly_series,
        "fav_weekday": fav_weekday,
        "longest_streak": {
            "days": longest_streak,
            "start": streak_start_date.isoformat() if streak_start_date else None,
            "end": streak_end_date.isoformat() if streak_end_date else None,
        } if longest_streak > 0 else None,
        "biggest_distance": biggest_run,
        "longest_workout": longest_workout,
    }
