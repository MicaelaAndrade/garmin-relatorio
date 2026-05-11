"""Le tabelas vo2max e race_predictions (alimentadas pelo ingest do export GDPR)."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..db import connect


def vo2max_series(days: int = 365, sport: str = "run") -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, value FROM vo2max
            WHERE sport = ? AND date >= ?
            ORDER BY date
            """,
            conn,
            params=(sport, cutoff),
        )
    return df.to_dict(orient="records") if not df.empty else []


def latest_vo2max() -> dict:
    with connect() as conn:
        df = pd.read_sql_query(
            "SELECT date, sport, value FROM vo2max ORDER BY date DESC LIMIT 5",
            conn,
        )
    if df.empty:
        return {"by_sport": {}}
    by_sport = {}
    for sport, sub in df.groupby("sport"):
        latest = sub.iloc[0]
        by_sport[sport] = {"date": latest["date"], "value": float(latest["value"])}
    return {"by_sport": by_sport}


def garmin_race_predictions() -> dict:
    """Pega a predicao mais recente que o Garmin calculou."""
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, race_5k_s, race_10k_s, race_half_s, race_marathon_s
            FROM race_predictions
            WHERE race_5k_s IS NOT NULL
            ORDER BY date DESC
            LIMIT 1
            """,
            conn,
        )
    if df.empty:
        return {"date": None, "predictions": []}
    row = df.iloc[0]
    distances = [
        ("5K", 5000, "race_5k_s"),
        ("10K", 10000, "race_10k_s"),
        ("21K", 21097, "race_half_s"),
        ("Maratona", 42195, "race_marathon_s"),
    ]
    return {
        "date": row["date"],
        "predictions": [
            {
                "label": label,
                "distance_m": dist,
                "predicted_time_s": int(row[col]),
                "predicted_pace_s_km": round(int(row[col]) / (dist / 1000.0), 1),
            }
            for label, dist, col in distances
            if pd.notna(row[col])
        ],
    }


def garmin_predictions_series(days: int = 180) -> list[dict]:
    """Evolucao das predicoes ao longo do tempo (mostra se voce esta progredindo)."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, race_5k_s, race_10k_s, race_half_s, race_marathon_s
            FROM race_predictions
            WHERE date >= ? AND race_5k_s IS NOT NULL
            ORDER BY date
            """,
            conn,
            params=(cutoff,),
        )
    if df.empty:
        return []
    # 1 ponto por dia (Garmin atualiza varias vezes ao dia, pega ultimo do dia)
    df = df.groupby("date").last().reset_index()
    return df.to_dict(orient="records")
