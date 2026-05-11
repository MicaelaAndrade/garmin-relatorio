"""Body battery + stress diário do Garmin."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..db import connect


def wellness_dashboard(days: int = 30) -> dict[str, Any]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT date, body_battery, stress_avg, resting_hr, hrv_overnight
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
    }
