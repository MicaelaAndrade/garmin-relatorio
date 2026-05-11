"""Planejamento de provas: countdown, predicao Garmin pra distancia, sugestoes peak/taper.

Heuristica de fase de treino baseada em semanas restantes:
  >= 8 semanas: BASE — construir volume aerobico
  4-8 semanas: BUILD — adicionar intensidade
  2-4 semanas: PEAK — pico de carga, especificidade
  1-2 semanas: TAPER — reduzir 30-40% volume, manter intensidade
  ultima semana: RACE WEEK — descanso ativo
"""
from __future__ import annotations

from datetime import date, datetime

from . import garmin_metrics
from ..db import connect


def list_races(include_past: bool = False) -> list[dict]:
    with connect() as conn:
        if include_past:
            rows = conn.execute(
                "SELECT * FROM races ORDER BY race_date"
            ).fetchall()
        else:
            today = date.today().isoformat()
            rows = conn.execute(
                "SELECT * FROM races WHERE race_date >= ? ORDER BY race_date",
                (today,),
            ).fetchall()
    today = date.today()
    out = []
    for r in rows:
        race_date = datetime.fromisoformat(r["race_date"]).date()
        days_to = (race_date - today).days
        weeks_to = max(0, days_to // 7)
        phase = _phase(weeks_to)
        out.append({
            **dict(r),
            "days_to": days_to,
            "weeks_to": weeks_to,
            "phase": phase,
            "phase_message": _phase_message(phase, weeks_to),
            "garmin_prediction": _garmin_prediction_for(r),
        })
    return out


def _phase(weeks_to: int) -> str:
    if weeks_to >= 8:
        return "base"
    if weeks_to >= 4:
        return "build"
    if weeks_to >= 2:
        return "peak"
    if weeks_to >= 1:
        return "taper"
    return "race_week"


def _phase_message(phase: str, weeks_to: int) -> str:
    msgs = {
        "base": "Foco em volume aerobico (Z1-Z2). Construa base. Inclua 1-2 longos por semana.",
        "build": "Adicione intensidade: tempo runs (Z3), intervalos (Z4). Mantenha 1 longo/semana.",
        "peak": (
            "Pico de carga. Treinos especificos da prova "
            "(ex: simulacao de pace). Cuide bem do sono."
        ),
        "taper": (
            "TAPER: reduza volume 30-40%, mantenha intensidade. "
            "Foco em recuperacao e qualidade."
        ),
        "race_week": "Semana da prova! Descanso ativo. Hidratacao, sono, comida conhecida.",
    }
    return msgs.get(phase, "")


def _garmin_prediction_for(race_row) -> dict | None:
    """Pega predicao do Garmin pra distancia da prova (corridas)."""
    sport = race_row["sport"]
    if sport != "run":
        return None
    dist = race_row["distance_m"]
    if not dist:
        return None

    pred = garmin_metrics.garmin_race_predictions()
    # Match a distancia mais proxima
    if not pred or not pred.get("predictions"):
        return None
    closest = min(
        pred["predictions"], key=lambda p: abs(p["distance_m"] - dist)
    )
    diff_pct = abs(closest["distance_m"] - dist) / dist * 100
    if diff_pct > 30:
        return None  # muito distante pra ser util
    return {
        "predicted_time_s": closest["predicted_time_s"],
        "predicted_pace_s_km": closest["predicted_pace_s_km"],
        "based_on_label": closest["label"],
        "base_distance_m": closest["distance_m"],
        "approximation": diff_pct > 5,
    }


def add_race(
    name: str,
    race_date: str,
    sport: str,
    distance_m: float | None = None,
    location: str | None = None,
    notes: str | None = None,
    target_time_s: int | None = None,
    is_confirmed: int = 1,
    triathlon_swim_m: float | None = None,
    triathlon_bike_m: float | None = None,
    triathlon_run_m: float | None = None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO races
            (name, race_date, sport, distance_m, triathlon_swim_m,
             triathlon_bike_m, triathlon_run_m, location, target_time_s, notes, is_confirmed)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                name, race_date, sport, distance_m,
                triathlon_swim_m, triathlon_bike_m, triathlon_run_m,
                location, target_time_s, notes, is_confirmed,
            ),
        )
        return int(cur.lastrowid or 0)


def delete_race(race_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM races WHERE id = ?", (race_id,))
        return cur.rowcount > 0
