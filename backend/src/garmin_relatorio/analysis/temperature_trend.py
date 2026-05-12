"""Trend de temperatura ambiente nos treinos.

Garmin grava minTemperature/maxTemperature em °C no raw das atividades.
Pra cada +1°C acima de 25°C, FC sobe ~1bpm no mesmo pace (heat strain).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pandas as pd

from ..db import connect


def temperature_trend(days: int = 90) -> dict[str, Any]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT started_at, sport, duration_s, avg_hr, avg_pace_s_km, raw
            FROM activities
            WHERE started_at >= ?
              AND sport IN ('run', 'bike')
              AND duration_s > 600
            """,
            conn,
            params=(cutoff,),
        )
    if df.empty:
        return {"available": False, "reason": "Sem atividades cardio no período."}

    def _extract_temp(raw: str | None) -> tuple[float | None, float | None]:
        if not raw:
            return None, None
        try:
            r = json.loads(raw)
            return r.get("minTemperature"), r.get("maxTemperature")
        except json.JSONDecodeError:
            return None, None

    df["min_t"], df["max_t"] = zip(*df["raw"].apply(_extract_temp))
    df = df.dropna(subset=["min_t", "max_t"])
    if df.empty:
        return {"available": False, "reason": "Atividades sem dados de temperatura."}

    df["avg_t"] = (df["min_t"] + df["max_t"]) / 2
    df["date"] = pd.to_datetime(df["started_at"]).dt.date

    series = [
        {
            "date": row.date.isoformat(),
            "sport": row.sport,
            "avg_temp_c": round(float(row.avg_t), 1),
            "max_temp_c": round(float(row.max_t), 1),
            "avg_hr": int(row.avg_hr) if pd.notna(row.avg_hr) else None,
            "avg_pace_s_km": int(row.avg_pace_s_km) if pd.notna(row.avg_pace_s_km) else None,
        }
        for row in df.sort_values("date").itertuples()
    ]

    avg_temp = round(float(df["avg_t"].mean()), 1)
    max_temp = round(float(df["max_t"].max()), 1)
    hot_days = int((df["max_t"] >= 30).sum())
    cool_days = int((df["max_t"] < 20).sum())

    # Correlação simples: FC vs temperatura em corridas
    insight = None
    runs = df[(df["sport"] == "run") & df["avg_hr"].notna()]
    if len(runs) >= 8:
        hot = runs[runs["avg_t"] >= 28]
        cool = runs[runs["avg_t"] < 25]
        if len(hot) >= 3 and len(cool) >= 3:
            hot_hr = float(hot["avg_hr"].mean())
            cool_hr = float(cool["avg_hr"].mean())
            diff = round(hot_hr - cool_hr, 1)
            if abs(diff) >= 2:
                insight = (
                    f"Em treinos quentes (≥28°C, {len(hot)} sessões) sua FC média foi {hot_hr:.0f}bpm; "
                    f"em frescos (<25°C, {len(cool)} sessões) foi {cool_hr:.0f}bpm. "
                    f"Diferença: {diff:+.1f}bpm — heat strain {'forte' if abs(diff) > 5 else 'visível'}."
                )

    return {
        "available": True,
        "days": days,
        "series": series,
        "avg_temp_c": avg_temp,
        "max_temp_c": max_temp,
        "hot_days_30plus": hot_days,
        "cool_days_under20": cool_days,
        "total_sessions": int(len(df)),
        "insight": insight,
    }
