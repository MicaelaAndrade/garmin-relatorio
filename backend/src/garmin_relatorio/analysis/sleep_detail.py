"""Sono detalhado: deep/light/REM/awake, eficiencia, scores."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..db import connect


def sleep_detail(days: int = 30) -> dict[str, Any]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT date, total_min, deep_min, light_min, rem_min, awake_min, score
            FROM sleep
            WHERE date >= ?
            ORDER BY date
            """,
            (cutoff,),
        ).fetchall()

    series: list[dict] = []
    totals = {"total": 0, "deep": 0, "light": 0, "rem": 0, "awake": 0, "score": 0}
    counts = {"score": 0, "stages": 0}
    short_count = 0    # noites < 6h
    low_score_count = 0  # score < 50
    for r in rows:
        total = r["total_min"] or 0
        awake = r["awake_min"] or 0
        deep = r["deep_min"] or 0
        light = r["light_min"] or 0
        rem = r["rem_min"] or 0
        eff = round(total / (total + awake) * 100) if total + awake > 0 else None
        series.append({
            "date": r["date"],
            "total_min": total,
            "deep_min": deep,
            "light_min": light,
            "rem_min": rem,
            "awake_min": awake,
            "total_h": round(total / 60, 1),
            "deep_pct": round(deep / total * 100, 1) if total else 0,
            "rem_pct": round(rem / total * 100, 1) if total else 0,
            "efficiency_pct": eff,
            "score": r["score"],
        })
        if total < 360 and total > 0:
            short_count += 1
        if r["score"] and r["score"] < 50:
            low_score_count += 1
        if total > 0:
            totals["total"] += total
            totals["deep"] += deep
            totals["light"] += light
            totals["rem"] += rem
            totals["awake"] += awake
            counts["stages"] += 1
        if r["score"]:
            totals["score"] += r["score"]
            counts["score"] += 1

    if counts["stages"] == 0:
        return {
            "available": False,
            "days": days,
            "series": [],
        }

    avg_total = totals["total"] / counts["stages"]
    avg_total_h = round(avg_total / 60, 1)
    avg_deep_pct = round(totals["deep"] / totals["total"] * 100, 1)
    avg_rem_pct = round(totals["rem"] / totals["total"] * 100, 1)
    avg_efficiency = round(
        totals["total"] / (totals["total"] + totals["awake"]) * 100, 1
    ) if totals["total"] + totals["awake"] > 0 else None
    avg_score = round(totals["score"] / counts["score"]) if counts["score"] else None

    # Veredito qualidade
    if avg_total_h >= 7.5 and avg_efficiency and avg_efficiency >= 88:
        verdict = "excelente"
        message = "Sono em dia: duração ideal e eficiência alta."
    elif avg_total_h >= 7.0:
        verdict = "bom"
        message = "Duração adequada. Atenção pra eficiência e estágios profundos."
    elif avg_total_h >= 6.0:
        verdict = "regular"
        message = "Sono curto. Aumentar 30-60min por noite ajuda recuperação."
    else:
        verdict = "ruim"
        message = "Sono muito curto. Prioridade na rotina pra evitar overtraining."

    return {
        "available": True,
        "days": days,
        "series": series,
        "avg_total_h": avg_total_h,
        "avg_total_min": int(avg_total),
        "avg_deep_pct": avg_deep_pct,
        "avg_rem_pct": avg_rem_pct,
        "avg_efficiency_pct": avg_efficiency,
        "avg_score": avg_score,
        "nights_short": short_count,
        "nights_low_score": low_score_count,
        "verdict": verdict,
        "message": message,
    }
