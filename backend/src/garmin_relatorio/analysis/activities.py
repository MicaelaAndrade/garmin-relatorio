"""Listagem de atividades recentes + agregado diario para calendar heatmap."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from ..db import connect


def recent_activities(limit: int = 20) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, source, external_id, sport, started_at,
                   duration_s, distance_m, avg_hr, max_hr,
                   avg_pace_s_km, elevation_gain, calories, raw
            FROM activities
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        # extrai nome da atividade do raw quando disponivel
        try:
            raw = json.loads(d.pop("raw") or "{}")
            d["name"] = raw.get("name") or raw.get("activityName")
            from .zones_distribution import zones_from_raw
            zones = zones_from_raw(raw)
            if zones:
                d["zones_s"] = zones
        except Exception:
            d["name"] = None
        out.append(d)
    return out


def daily_load_calendar(days: int = 180) -> list[dict]:
    """1 ponto por dia: total de minutos + carga TRIMP. Usado pra heatmap."""
    from .hr_zones import trimp_for_activity

    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT started_at, sport, duration_s, distance_m, avg_hr
            FROM activities
            WHERE started_at >= ?
            ORDER BY started_at
            """,
            conn,
            params=(cutoff,),
        )
    if df.empty:
        return []
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["day"] = df["started_at"].dt.date
    df["duration_min"] = df["duration_s"] / 60.0
    df["load"] = df.apply(
        lambda r: trimp_for_activity(r["duration_min"], r["avg_hr"]), axis=1
    )

    grouped = df.groupby("day").agg(
        sessions=("started_at", "count"),
        duration_min=("duration_min", "sum"),
        load=("load", "sum"),
        sports=("sport", lambda s: ",".join(sorted(set(s)))),
    ).reset_index()

    full_range = pd.date_range(grouped["day"].min(), date.today(), freq="D").date
    grouped = grouped.set_index("day").reindex(full_range).reset_index()
    grouped.columns = ["day", "sessions", "duration_min", "load", "sports"]
    grouped["sessions"] = grouped["sessions"].fillna(0).astype(int)
    grouped["duration_min"] = grouped["duration_min"].fillna(0).round(0)
    grouped["load"] = grouped["load"].fillna(0).round(1)
    grouped["sports"] = grouped["sports"].fillna("")

    return [
        {
            "day": row.day.isoformat(),
            "sessions": int(row.sessions),
            "duration_min": float(row.duration_min),
            "load": float(row.load),
            "sports": row.sports,
        }
        for row in grouped.itertuples()
    ]
