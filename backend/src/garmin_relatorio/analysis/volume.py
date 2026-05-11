"""Agregacao de volume e intensidade por modalidade.

Volume = soma de duracao (min) e distancia (km) por semana, separado por sport.
Pace medio ponderado pela distancia.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from ..db import connect


def load_activities_df(days: int = 180) -> pd.DataFrame:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT id, source, sport, started_at, duration_s, distance_m,
                   avg_hr, avg_pace_s_km, training_load
            FROM activities
            WHERE started_at >= ?
            ORDER BY started_at
            """,
            conn,
            params=(cutoff,),
        )
    if df.empty:
        return df
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["week_start"] = df["started_at"].dt.to_period("W-MON").dt.start_time.dt.date
    df["distance_km"] = df["distance_m"].fillna(0) / 1000.0
    df["duration_min"] = df["duration_s"] / 60.0
    return df


def weekly_summary(days: int = 90) -> list[dict]:
    """Volume semanal por modalidade."""
    df = load_activities_df(days)
    if df.empty:
        return []

    grouped = df.groupby(["week_start", "sport"]).agg(
        sessions=("id", "count"),
        duration_min=("duration_min", "sum"),
        distance_km=("distance_km", "sum"),
        avg_hr=("avg_hr", "mean"),
    ).reset_index()

    return [
        {
            "week_start": row.week_start.isoformat(),
            "sport": row.sport,
            "sessions": int(row.sessions),
            "duration_min": round(float(row.duration_min), 1),
            "distance_km": round(float(row.distance_km), 2),
            "avg_hr": round(float(row.avg_hr), 0) if pd.notna(row.avg_hr) else None,
        }
        for row in grouped.itertuples()
    ]


def latest_week_totals() -> dict:
    """Totais da semana corrente (segunda → hoje)."""
    df = load_activities_df(14)
    if df.empty:
        return {"sessions": 0, "duration_min": 0, "distance_km": 0, "by_sport": {}}

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    df_week = df[df["started_at"].dt.date >= week_start]

    by_sport = {}
    for sport, sub in df_week.groupby("sport"):
        by_sport[sport] = {
            "sessions": int(len(sub)),
            "duration_min": round(float(sub["duration_min"].sum()), 1),
            "distance_km": round(float(sub["distance_km"].sum()), 2),
        }

    return {
        "week_start": week_start.isoformat(),
        "sessions": int(len(df_week)),
        "duration_min": round(float(df_week["duration_min"].sum()), 1),
        "distance_km": round(float(df_week["distance_km"].sum()), 2),
        "by_sport": by_sport,
    }
