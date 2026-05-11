"""Predicao de performance: pace de prova via formula de Riegel.

T2 = T1 * (D2/D1)^1.06

T1 = melhor tempo recente em distancia D1
D2 = distancia alvo (ex: 5k, 10k, 21k)
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..db import connect

RIEGEL_EXP = 1.06

# Distancias alvo por modalidade (m)
TARGETS = {
    "run": [5000, 10000, 21097, 42195],
    "swim": [750, 1500, 3800],
    "bike": [20000, 40000, 90000, 180000],
}


def best_recent_efforts(days: int = 60, sport: str = "run") -> list[dict]:
    """Pega os melhores paces recentes acima de 1km/min de duracao significativa."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT started_at, distance_m, duration_s, avg_pace_s_km
            FROM activities
            WHERE started_at >= ? AND sport = ? AND distance_m > 1000
            ORDER BY avg_pace_s_km ASC
            LIMIT 5
            """,
            conn,
            params=(cutoff, sport),
        )
    return df.to_dict(orient="records") if not df.empty else []


def predict_race(sport: str = "run") -> dict:
    """Para cada distancia alvo, prediz tempo via Riegel a partir do melhor recente."""
    bests = best_recent_efforts(60, sport)
    if not bests:
        return {"sport": sport, "reference": None, "predictions": []}

    ref = bests[0]
    t1 = float(ref["duration_s"])
    d1 = float(ref["distance_m"])

    preds = []
    for d2 in TARGETS.get(sport, []):
        if abs(d2 - d1) / d1 > 0.5:
            confidence = "baixa"
        elif abs(d2 - d1) / d1 > 0.2:
            confidence = "media"
        else:
            confidence = "alta"
        t2 = t1 * (d2 / d1) ** RIEGEL_EXP
        preds.append(
            {
                "distance_m": d2,
                "predicted_time_s": round(t2),
                "predicted_pace_s_km": round(t2 / (d2 / 1000.0), 1),
                "confidence": confidence,
            }
        )

    return {
        "sport": sport,
        "reference": {
            "started_at": ref["started_at"],
            "distance_m": d1,
            "duration_s": int(t1),
            "pace_s_km": round(t1 / (d1 / 1000.0), 1),
        },
        "predictions": preds,
    }
