"""Evolucao de pace mensal por modalidade (corrida, nado) e velocidade (bike)."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..db import connect


def monthly_pace_evolution(days: int = 365) -> dict:
    """Para cada mes: pace medio ponderado pela distancia.

    Outliers: ignora atividades < 1km (warmups, testes).
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT sport, started_at, distance_m, duration_s, avg_hr, avg_cadence
            FROM activities
            WHERE started_at >= ? AND sport IN ('run','swim','bike')
              AND distance_m > 1000 AND duration_s > 300
            """,
            conn,
            params=(cutoff,),
        )
    if df.empty:
        return {"run": [], "swim": [], "bike": []}

    df["started_at"] = pd.to_datetime(df["started_at"])
    df["month"] = df["started_at"].dt.to_period("M").dt.start_time.dt.date

    out: dict[str, list[dict]] = {"run": [], "swim": [], "bike": []}
    for sport in ["run", "swim", "bike"]:
        sub = df[df["sport"] == sport]
        if sub.empty:
            continue
        for month, g in sub.groupby("month"):
            total_dist = float(g["distance_m"].sum())
            total_time = float(g["duration_s"].sum())
            if total_dist <= 0 or total_time <= 0:
                continue
            row = {
                "month": month.isoformat(),
                "sessions": int(len(g)),
                "total_km": round(total_dist / 1000, 1),
                "avg_hr": round(float(g["avg_hr"].mean()), 0)
                if g["avg_hr"].notna().any()
                else None,
                "avg_cadence": round(float(g["avg_cadence"].mean()), 1)
                if g["avg_cadence"].notna().any()
                else None,
            }
            if sport == "bike":
                # km/h media ponderada
                row["avg_speed_kmh"] = round((total_dist / 1000) / (total_time / 3600), 2)
            else:
                # s/km (corrida) ou s/100m (nado, mas mantemos s/km e front converte)
                row["avg_pace_s_km"] = round(total_time / (total_dist / 1000), 1)
            out[sport].append(row)

    return out
