"""Sono + HR repouso + HRV. Cruza com proximo treino para flag de readiness."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..db import connect


def sleep_series(days: int = 30) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, total_min, deep_min, rem_min, score
            FROM sleep
            WHERE date >= ?
            ORDER BY date
            """,
            conn,
            params=(cutoff,),
        )
    if df.empty:
        return []
    df["total_h"] = (df["total_min"] / 60).round(2)
    return df.to_dict(orient="records")


def daily_metrics_series(days: int = 30) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, resting_hr, hrv_overnight, body_battery, stress_avg, steps
            FROM daily_metrics
            WHERE date >= ?
            ORDER BY date
            """,
            conn,
            params=(cutoff,),
        )
    return df.to_dict(orient="records") if not df.empty else []


def readiness_today() -> dict:
    """Flag simples de prontidao baseada em sono ultimas 3 noites + HR repouso vs baseline."""
    sleep = sleep_series(7)
    metrics = daily_metrics_series(28)

    if not sleep or not metrics:
        return {"score": None, "flag": "sem_dados", "notes": []}

    notes = []
    last_3_sleep_h = [s["total_h"] for s in sleep[-3:] if s["total_h"]]
    avg_3 = sum(last_3_sleep_h) / len(last_3_sleep_h) if last_3_sleep_h else 0
    if avg_3 < 6.5:
        notes.append(f"Sono medio 3 noites: {avg_3:.1f}h (alvo >7h)")

    rhrs = [m["resting_hr"] for m in metrics if m["resting_hr"]]
    if len(rhrs) >= 14:
        baseline = sum(rhrs[:-3]) / len(rhrs[:-3])
        recent = sum(rhrs[-3:]) / 3
        if recent > baseline + 5:
            notes.append(f"HR repouso elevado: {recent:.0f} vs baseline {baseline:.0f}")

    score = "verde"
    if len(notes) == 1:
        score = "amarelo"
    elif len(notes) >= 2:
        score = "vermelho"

    return {"flag": score, "notes": notes}
