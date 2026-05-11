"""Calorias: gasto diário (BMR + ativo), por treino e por modalidade.

Fontes:
- daily_metrics.total_kcal / active_kcal / bmr_kcal: gasto total do dia (Garmin)
- activities.calories: gasto por sessão (já em kcal após fix kJ->kcal pro export)

A função kcal/h por modalidade dá referência pra estimar gasto antes do treino.
"""
from __future__ import annotations

from datetime import date, timedelta
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


def calories_dashboard(days: int = 30) -> dict[str, Any]:
    today = date.today()
    cutoff = (today - timedelta(days=days)).isoformat()

    with connect() as conn:
        daily_df = pd.read_sql_query(
            """
            SELECT date, total_kcal, active_kcal, bmr_kcal, steps
            FROM daily_metrics
            WHERE total_kcal IS NOT NULL AND date >= ?
            ORDER BY date
            """,
            conn,
            params=(cutoff,),
        )
        per_sport_df = pd.read_sql_query(
            """
            SELECT sport, calories, duration_s
            FROM activities
            WHERE calories IS NOT NULL AND duration_s > 600
              AND started_at >= ?
            """,
            conn,
            params=(cutoff,),
        )

    daily_series = []
    if not daily_df.empty:
        for row in daily_df.itertuples():
            daily_series.append({
                "date": row.date,
                "total": int(row.total_kcal) if pd.notna(row.total_kcal) else None,
                "active": int(row.active_kcal) if pd.notna(row.active_kcal) else None,
                "bmr": int(row.bmr_kcal) if pd.notna(row.bmr_kcal) else None,
            })

    # Atual = ultimo dia com dado
    current = daily_series[-1] if daily_series else None
    # Médias do período
    avg_total = int(daily_df["total_kcal"].mean()) if not daily_df.empty else None
    avg_active = int(daily_df["active_kcal"].mean()) if not daily_df.empty and daily_df["active_kcal"].notna().any() else None
    avg_bmr = int(daily_df["bmr_kcal"].mean()) if not daily_df.empty and daily_df["bmr_kcal"].notna().any() else None

    # Por modalidade: kcal/h ponderado
    by_sport = []
    if not per_sport_df.empty:
        per_sport_df["kcal_per_h"] = per_sport_df["calories"] * 3600.0 / per_sport_df["duration_s"]
        grouped = per_sport_df.groupby("sport").agg(
            sessions=("calories", "count"),
            total_kcal=("calories", "sum"),
            avg_kcal_per_session=("calories", "mean"),
            avg_kcal_per_h=("kcal_per_h", "mean"),
        ).reset_index()
        # Sort: mais utilizado primeiro
        grouped = grouped.sort_values("total_kcal", ascending=False)
        for r in grouped.itertuples():
            by_sport.append({
                "sport": r.sport,
                "label": SPORT_LABEL.get(r.sport, r.sport),
                "sessions": int(r.sessions),
                "total_kcal": int(r.total_kcal),
                "avg_per_session": int(r.avg_kcal_per_session),
                "avg_per_hour": int(r.avg_kcal_per_h),
            })

    # Soma semanal (segunda da semana atual)
    monday = today - timedelta(days=today.weekday())
    week_df = daily_df[daily_df["date"] >= monday.isoformat()] if not daily_df.empty else daily_df
    week_total = int(week_df["total_kcal"].sum()) if not week_df.empty else 0
    week_active = int(week_df["active_kcal"].sum()) if not week_df.empty and week_df["active_kcal"].notna().any() else 0

    return {
        "available": current is not None,
        "days": days,
        "current": current,
        "average": {
            "total": avg_total,
            "active": avg_active,
            "bmr": avg_bmr,
        },
        "week_total_kcal": week_total,
        "week_active_kcal": week_active,
        "daily_series": daily_series,
        "by_sport": by_sport,
    }
