"""Parser de arquivos .fit baixados manualmente do Garmin Connect.

Uso: coloque arquivos em backend/data/exports/*.fit e rode:
    garmin-relatorio ingest-fit
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from fitparse import FitFile

from ..config import ROOT
from ..db import connect

log = logging.getLogger(__name__)

EXPORTS_DIR = ROOT / "backend" / "data" / "exports"

SPORT_MAP = {
    "running": "run",
    "cycling": "bike",
    "swimming": "swim",
}


def ingest_directory(directory: Path | None = None) -> dict[str, int]:
    target = directory or EXPORTS_DIR
    target.mkdir(parents=True, exist_ok=True)

    files = list(target.glob("*.fit"))
    log.info("Encontrados %d arquivos .fit em %s", len(files), target)

    inserted = updated = 0
    with connect() as conn:
        for fit_path in files:
            session = _parse_session(fit_path)
            if not session:
                continue
            cur = conn.execute(
                """
                INSERT INTO activities (
                    source, external_id, sport, started_at, duration_s, distance_m,
                    avg_hr, max_hr, avg_pace_s_km, elevation_gain, calories, training_load, raw
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    duration_s=excluded.duration_s,
                    distance_m=excluded.distance_m
                """,
                (
                    "fit",
                    fit_path.stem,
                    session["sport"],
                    session["started_at"],
                    session["duration_s"],
                    session.get("distance_m"),
                    session.get("avg_hr"),
                    session.get("max_hr"),
                    session.get("avg_pace_s_km"),
                    session.get("elevation_gain"),
                    session.get("calories"),
                    None,
                    json.dumps(session, default=str),
                ),
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1

    return {"inserted": inserted, "updated": updated}


def _parse_session(fit_path: Path) -> dict | None:
    """Extrai a session principal do FIT. Um FIT geralmente tem 1 session."""
    fit = FitFile(str(fit_path))
    sessions = list(fit.get_messages("session"))
    if not sessions:
        return None

    s = {f.name: f.value for f in sessions[0]}
    sport_raw = str(s.get("sport") or "").lower()
    sport = SPORT_MAP.get(sport_raw, "other")
    started: datetime | None = s.get("start_time")
    duration = s.get("total_elapsed_time") or 0
    distance = s.get("total_distance")
    pace = (
        float(duration) / (float(distance) / 1000.0)
        if distance and distance > 0 and sport != "bike"
        else None
    )

    return {
        "sport": sport,
        "started_at": started.isoformat() if started else "",
        "duration_s": int(duration),
        "distance_m": float(distance) if distance else None,
        "avg_hr": int(s["avg_heart_rate"]) if s.get("avg_heart_rate") else None,
        "max_hr": int(s["max_heart_rate"]) if s.get("max_heart_rate") else None,
        "avg_pace_s_km": pace,
        "elevation_gain": float(s["total_ascent"]) if s.get("total_ascent") else None,
        "calories": int(s["total_calories"]) if s.get("total_calories") else None,
    }
