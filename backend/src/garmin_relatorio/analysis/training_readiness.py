"""Training Readiness + Training Status do Garmin (FR265).

Le as tabelas alimentadas por ingest.garmin.ingest_training_readiness /
ingest_training_status. Readiness e uma serie diaria (score 0-100 + nivel);
Training Status e o snapshot mais recente (PRODUCTIVE etc) com o ACWR oficial
do Garmin — util pra cruzar com o ACWR caseiro (analysis/acwr.py).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..db import connect

_LEVEL_PT = {
    "MAXIMUM": "Máximo",
    "HIGH": "Alto",
    "MODERATE": "Moderado",
    "LOW": "Baixo",
    "VERY_LOW": "Muito baixo",
    "POOR": "Ruim",
}

_STATUS_PT = {
    "PRODUCTIVE": "Produtivo",
    "MAINTAINING": "Mantendo",
    "RECOVERY": "Recuperação",
    "PEAKING": "Em pico",
    "OVERREACHING": "Overreaching",
    "UNPRODUCTIVE": "Improdutivo",
    "DETRAINING": "Destreino",
    "STRAINED": "Sobrecarregado",
    "NO_STATUS": "Sem status",
}

_ACWR_PT = {
    "OPTIMAL": "Ótimo",
    "LOW": "Baixo",
    "HIGH": "Alto",
    "VERY_HIGH": "Muito alto",
}


def _humanize(code: str | None) -> str | None:
    """Fallback legivel pra feedback nao mapeado (ex: LOW_HRV_UNBALANCED)."""
    if not code:
        return None
    return code.replace("_", " ").capitalize()


def _status_label(phrase: str | None) -> str | None:
    if not phrase:
        return None
    prefix = phrase.rsplit("_", 1)[0] if phrase[-1:].isdigit() else phrase
    return _STATUS_PT.get(prefix, _humanize(phrase))


def training_readiness_dashboard(days: int = 30) -> dict[str, Any]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT date, score, level, feedback_short, feedback_long, sleep_score,
                   recovery_time, hrv_factor, acute_load, acwr_factor, stress_factor
            FROM training_readiness
            WHERE date >= ?
            ORDER BY date
            """,
            (cutoff,),
        ).fetchall()
        status = conn.execute(
            """
            SELECT date, status_code, status_phrase, acwr_percent, acwr_status,
                   acute_load, chronic_max, chronic_min, fitness_trend
            FROM training_status
            ORDER BY date DESC LIMIT 1
            """
        ).fetchone()

    if not rows and not status:
        return {"available": False, "days": days, "series": []}

    series = [{"date": r["date"], "score": r["score"], "level": r["level"]} for r in rows]
    scores = [r["score"] for r in rows if r["score"] is not None]

    latest = None
    if rows:
        r = rows[-1]
        latest = {
            "date": r["date"],
            "score": r["score"],
            "level": r["level"],
            "level_pt": _LEVEL_PT.get(r["level"], _humanize(r["level"])),
            "feedback": _humanize(r["feedback_long"]) or _humanize(r["feedback_short"]),
            "sleep_score": r["sleep_score"],
            "recovery_time_h": round(r["recovery_time"] / 60, 1) if r["recovery_time"] else None,
            "hrv_factor": r["hrv_factor"],
            "acute_load": r["acute_load"],
            "acwr_factor": r["acwr_factor"],
            "stress_factor": r["stress_factor"],
        }

    status_out = None
    if status:
        status_out = {
            "date": status["date"],
            "phrase": status["status_phrase"],
            "status_pt": _status_label(status["status_phrase"]),
            "acwr_percent": status["acwr_percent"],
            "acwr_status": status["acwr_status"],
            "acwr_status_pt": _ACWR_PT.get(status["acwr_status"], _humanize(status["acwr_status"])),
            "acute_load": status["acute_load"],
            "chronic_min": status["chronic_min"],
            "chronic_max": status["chronic_max"],
            "fitness_trend": status["fitness_trend"],
        }

    return {
        "available": True,
        "days": days,
        "series": series,
        "latest": latest,
        "status": status_out,
        "avg_score": round(sum(scores) / len(scores)) if scores else None,
    }
