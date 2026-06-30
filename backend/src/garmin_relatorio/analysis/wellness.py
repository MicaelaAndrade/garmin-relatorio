"""Body battery + stress diário do Garmin.

Inclui o snapshot mais recente de HRV Status (BALANCED + faixa de baseline),
SpO2 e respiração, extraídos do `raw` diário (Garmin já entrega; ver
ingest/garmin.py). São status pontuais — usamos o dia mais recente com dado.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from ..db import connect

_HRV_STATUS_PT = {
    "BALANCED": "Equilibrado",
    "UNBALANCED": "Desequilibrado",
    "LOW": "Baixo",
    "POOR": "Ruim",
    "NOT_ENOUGH_DATA": "Sem dados suficientes",
}


def _latest_status(rows: list) -> dict[str, Any] | None:
    """HRV Status / SpO2 / respiração do dia mais recente que tiver o dado no raw."""
    hrv_status = spo2 = respiration = None
    status_date = None
    for r in reversed(rows):  # mais recente primeiro
        try:
            raw = json.loads(r["raw"]) if r["raw"] else {}
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        summ = raw.get("summary") or {}
        hs = (raw.get("hrv") or {}).get("hrvSummary") or {}

        if hrv_status is None and hs.get("status"):
            base = hs.get("baseline") or {}
            hrv_status = {
                "status": hs.get("status"),
                "status_pt": _HRV_STATUS_PT.get(hs.get("status"), hs.get("status")),
                "weekly_avg": hs.get("weeklyAvg"),
                "last_night_avg": hs.get("lastNightAvg"),
                "baseline_low": base.get("lowUpper"),
                "balanced_low": base.get("balancedLow"),
                "balanced_upper": base.get("balancedUpper"),
            }
            status_date = r["date"]
        if spo2 is None and summ.get("averageSpo2") is not None:
            spo2 = {
                "avg": summ.get("averageSpo2"),
                "lowest": summ.get("lowestSpo2"),
                "latest": summ.get("latestSpo2"),
            }
        if respiration is None and summ.get("avgWakingRespirationValue") is not None:
            respiration = {
                "avg_waking": summ.get("avgWakingRespirationValue"),
                "lowest": summ.get("lowestRespirationValue"),
                "highest": summ.get("highestRespirationValue"),
            }
        if hrv_status and spo2 and respiration:
            break

    if not (hrv_status or spo2 or respiration):
        return None
    return {
        "date": status_date,
        "hrv_status": hrv_status,
        "spo2": spo2,
        "respiration": respiration,
    }


def wellness_dashboard(days: int = 30) -> dict[str, Any]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT date, body_battery, stress_avg, resting_hr, hrv_overnight, raw
            FROM daily_metrics
            WHERE date >= ?
            ORDER BY date
            """,
            (cutoff,),
        ).fetchall()

    if not rows:
        return {"available": False, "days": days, "series": []}

    series = [
        {
            "date": r["date"],
            "body_battery": r["body_battery"],
            "stress": r["stress_avg"],
            "rhr": r["resting_hr"],
            "hrv": r["hrv_overnight"],
        }
        for r in rows
    ]

    bb_vals = [r["body_battery"] for r in rows if r["body_battery"] is not None]
    stress_vals = [r["stress_avg"] for r in rows if r["stress_avg"] is not None]
    rhr_vals = [r["resting_hr"] for r in rows if r["resting_hr"] is not None]
    hrv_vals = [r["hrv_overnight"] for r in rows if r["hrv_overnight"] is not None]

    return {
        "available": True,
        "days": days,
        "series": series,
        "avg_body_battery": round(sum(bb_vals) / len(bb_vals)) if bb_vals else None,
        "avg_stress": round(sum(stress_vals) / len(stress_vals)) if stress_vals else None,
        "avg_rhr": round(sum(rhr_vals) / len(rhr_vals)) if rhr_vals else None,
        "avg_hrv": round(sum(hrv_vals) / len(hrv_vals), 1) if hrv_vals else None,
        "stress_high_days": sum(1 for v in stress_vals if v >= 50),
        "bb_low_days": sum(1 for v in bb_vals if v < 50),
        "latest_status": _latest_status(rows),
    }
