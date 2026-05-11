"""Ingest do Garmin Connect via lib python-garminconnect.

A lib usa email/senha (e armazena tokens em ~/.garminconnect_session/ pra evitar
relogin a cada chamada — Garmin bloqueia login excessivo).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)

from ..config import ROOT, config
from ..db import connect

log = logging.getLogger(__name__)

SESSION_DIR = ROOT / "backend" / "data" / "garmin_session"

# Mapeia tipos de atividade do Garmin pro nosso enum interno.
# Mantem em sync com ingest/garmin_export.py SPORT_MAP.
SPORT_MAP = {
    "running": "run",
    "treadmill_running": "run",
    "trail_running": "run",
    "indoor_running": "run",
    "cycling": "bike",
    "road_biking": "bike",
    "indoor_cycling": "bike",
    "mountain_biking": "bike",
    "gravel_cycling": "bike",
    "lap_swimming": "swim",
    "open_water_swimming": "swim",
    "swimming": "swim",
    "yoga": "yoga",
    "pilates": "yoga",
    "meditation": "yoga",
    "breathwork": "yoga",
    "strength_training": "strength",
    "indoor_cardio": "strength",
    "walking": "walking",
    "hiking": "walking",
    "casual_walking": "walking",
    "indoor_walking": "walking",
}


def _extract_cadence_live(act: dict[str, Any], sport: str) -> float | None:
    """Campos retornados pela API live diferem do export."""
    if sport == "run":
        return (
            act.get("averageRunningCadenceInStepsPerMinute")
            or act.get("averageRunCadence")
        )
    if sport == "bike":
        return (
            act.get("averageBikingCadenceInRevPerMinute")
            or act.get("averageBikeCadence")
        )
    if sport == "swim":
        return (
            act.get("averageSwimCadenceInStrokesPerMinute")
            or act.get("averageSwolf")
        )
    return None


def _avg_speed_kmh(act: dict[str, Any], sport: str) -> float | None:
    if sport not in ("bike", "walking"):
        return None
    # API live: averageSpeed em m/s
    avg = act.get("averageSpeed")
    if avg:
        return round(float(avg) * 3.6, 2)
    duration = act.get("duration")
    distance = act.get("distance")
    if not duration or not distance or duration <= 0:
        return None
    return round((float(distance) / 1000.0) / (float(duration) / 3600.0), 2)


def login() -> Garmin:
    """Faz login com cache de sessao."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    try:
        api = Garmin(email=config.garmin_email, password=config.garmin_password)
        api.login(tokenstore=str(SESSION_DIR))
    except (GarminConnectAuthenticationError, GarminConnectConnectionError) as e:
        log.error("Falha no login do Garmin: %s", e)
        raise
    return api


def _normalize_sport(activity_type: str | None) -> str:
    if not activity_type:
        return "other"
    return SPORT_MAP.get(activity_type.lower(), "other")


def ingest_activities(days: int = 90, limit: int = 200) -> dict[str, int]:
    """Puxa atividades dos ultimos `days` dias."""
    api = login()
    activities: list[dict[str, Any]] = api.get_activities(0, limit)
    cutoff = datetime.now() - timedelta(days=days)

    inserted = updated = 0
    with connect() as conn:
        for act in activities:
            started = datetime.fromisoformat(act["startTimeLocal"])
            if started < cutoff:
                continue

            sport = _normalize_sport((act.get("activityType") or {}).get("typeKey"))
            row = (
                "garmin",
                str(act["activityId"]),
                sport,
                started.isoformat(),
                int(act.get("duration") or 0),
                act.get("distance"),
                int(act["averageHR"]) if act.get("averageHR") else None,
                int(act["maxHR"]) if act.get("maxHR") else None,
                _avg_pace(act, sport),
                _avg_speed_kmh(act, sport),
                _extract_cadence_live(act, sport),
                act.get("elevationGain"),
                int(act["calories"]) if act.get("calories") else None,
                act.get("activityTrainingLoad"),
                json.dumps(act, default=str),
            )
            cur = conn.execute(
                """
                INSERT INTO activities (
                    source, external_id, sport, started_at, duration_s, distance_m,
                    avg_hr, max_hr, avg_pace_s_km, avg_speed_kmh, avg_cadence,
                    elevation_gain, calories, training_load, raw
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source, external_id) DO UPDATE SET
                    sport=excluded.sport,
                    duration_s=excluded.duration_s,
                    distance_m=excluded.distance_m,
                    avg_hr=excluded.avg_hr,
                    max_hr=excluded.max_hr,
                    avg_pace_s_km=excluded.avg_pace_s_km,
                    avg_speed_kmh=excluded.avg_speed_kmh,
                    avg_cadence=excluded.avg_cadence,
                    elevation_gain=excluded.elevation_gain,
                    calories=excluded.calories,
                    training_load=excluded.training_load,
                    raw=excluded.raw
                """,
                row,
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                updated += 1

    log.info("Garmin activities: %d inseridas, %d atualizadas", inserted, updated)
    return {"inserted": inserted, "updated": updated}


def _avg_pace(act: dict[str, Any], sport: str) -> float | None:
    duration = act.get("duration")
    distance = act.get("distance")
    if not duration or not distance or distance <= 0:
        return None
    if sport == "bike":
        return None  # bike usa velocidade, nao pace
    # s/km
    return float(duration) / (float(distance) / 1000.0)


def ingest_sleep(days: int = 30) -> dict[str, int]:
    api = login()
    inserted = 0
    with connect() as conn:
        for offset in range(days):
            d = (date.today() - timedelta(days=offset + 1)).isoformat()
            try:
                data = api.get_sleep_data(d)
            except Exception as e:
                log.warning("Sleep falhou pra %s: %s", d, e)
                continue
            if not data or not data.get("dailySleepDTO"):
                continue
            dto = data["dailySleepDTO"]
            conn.execute(
                """
                INSERT OR REPLACE INTO sleep
                (date, total_min, deep_min, light_min, rem_min, awake_min, score, raw)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    d,
                    _seconds_to_min(dto.get("sleepTimeSeconds")),
                    _seconds_to_min(dto.get("deepSleepSeconds")),
                    _seconds_to_min(dto.get("lightSleepSeconds")),
                    _seconds_to_min(dto.get("remSleepSeconds")),
                    _seconds_to_min(dto.get("awakeSleepSeconds")),
                    (dto.get("sleepScores") or {}).get("overall", {}).get("value"),
                    json.dumps(data, default=str),
                ),
            )
            inserted += 1
    return {"inserted": inserted}


def ingest_daily(days: int = 30) -> dict[str, int]:
    """Puxa metricas diarias: HR repouso, HRV, body battery, stress, passos."""
    api = login()
    inserted = 0
    with connect() as conn:
        for offset in range(days):
            d = (date.today() - timedelta(days=offset + 1)).isoformat()
            try:
                summary = api.get_user_summary(d)
            except Exception as e:
                log.warning("Daily summary falhou pra %s: %s", d, e)
                continue
            if not summary:
                continue
            try:
                hrv = api.get_hrv_data(d)
                hrv_overnight = (hrv or {}).get("hrvSummary", {}).get("lastNightAvg")
            except Exception:
                hrv_overnight = None

            conn.execute(
                """
                INSERT OR REPLACE INTO daily_metrics
                (date, resting_hr, hrv_overnight, body_battery, stress_avg, steps,
                 total_kcal, active_kcal, bmr_kcal, raw)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    d,
                    summary.get("restingHeartRate"),
                    hrv_overnight,
                    summary.get("bodyBatteryHighestValue"),
                    summary.get("averageStressLevel"),
                    summary.get("totalSteps"),
                    int(summary["totalKilocalories"]) if summary.get("totalKilocalories") else None,
                    int(summary["activeKilocalories"]) if summary.get("activeKilocalories") else None,
                    int(summary["bmrKilocalories"]) if summary.get("bmrKilocalories") else None,
                    json.dumps({"summary": summary, "hrv": locals().get("hrv")}, default=str),
                ),
            )
            inserted += 1
    return {"inserted": inserted}


def ingest_scheduled_workouts(months_ahead: int = 2) -> dict[str, int]:
    """Puxa workouts agendados no calendario do Garmin Connect.

    Captura mes corrente + N meses adiante. Inclui treinos vindos de coach (Treius etc.)
    via integracoes parceiras.
    """
    api = login()
    inserted = 0
    today = date.today()

    months: list[tuple[int, int]] = []
    y, m = today.year, today.month
    for _ in range(months_ahead + 1):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    with connect() as conn:
        for year, month in months:
            try:
                payload = api.get_scheduled_workouts(year, month)
            except Exception as e:
                log.warning("Scheduled workouts %d-%02d falhou: %s", year, month, e)
                continue
            items = (payload or {}).get("calendarItems") or []
            for item in items:
                # Filtra: queremos workouts e corridas (eventos), nao atividades ja completadas
                item_type = item.get("itemType")
                if item_type not in ("workout", "event"):
                    continue
                date_str = item.get("date")
                if not date_str:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO scheduled_workouts
                    (id, workout_id, title, scheduled_date, sport_type,
                     duration_s, distance_m, is_race, raw)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        int(item.get("id")),
                        int(item["workoutId"]) if item.get("workoutId") else None,
                        item.get("title") or "(sem titulo)",
                        date_str,
                        item.get("sportTypeKey"),
                        int(item["duration"]) if item.get("duration") else None,
                        item.get("distance"),
                        1 if item.get("isRace") else 0,
                        json.dumps(item, default=str),
                    ),
                )
                inserted += 1

    log.info("Scheduled workouts: %d itens", inserted)
    return {"inserted": inserted}


def _flatten_workout_steps(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse workoutSegments preservando RepeatGroups.

    Cada nodo retornado tem `node_type`:
    - "step": passo executavel com {step_type, end_condition, end_value, target_type,
              target_value_one, target_value_two, zone_number, description}
    - "repeat": grupo de repeticao com {iterations, children: [nodos]}
    """

    def walk(steps: list[dict]) -> list[dict]:
        out: list[dict] = []
        for step in steps:
            if step.get("type") == "RepeatGroupDTO":
                out.append({
                    "node_type": "repeat",
                    "iterations": int(step.get("numberOfIterations") or 1),
                    "children": walk(step.get("workoutSteps") or []),
                })
                continue
            step_type = (step.get("stepType") or {}).get("stepTypeKey") or "other"
            end_cond = (step.get("endCondition") or {}).get("conditionTypeKey") or "lap.button"
            target = (step.get("targetType") or {}).get("workoutTargetTypeKey") or "no.target"
            out.append({
                "node_type": "step",
                "step_type": step_type,
                "end_condition": end_cond,
                "end_value": step.get("endConditionValue"),
                "target_type": target,
                "target_value_one": step.get("targetValueOne"),
                "target_value_two": step.get("targetValueTwo"),
                "zone_number": step.get("zoneNumber"),
                "description": step.get("description") or None,
            })
        return out

    nodes: list[dict] = []
    for seg in segments or []:
        nodes.extend(walk(seg.get("workoutSteps") or []))
    return nodes


def ingest_workout_details(workout_ids: list[int] | None = None, limit: int = 50) -> dict[str, int]:
    """Busca a estrutura completa (steps) de cada workout agendado.

    Se workout_ids for None: pega ids unicos de scheduled_workouts agendados
    nos proximos 21 dias que ainda nao tem detalhes salvos.
    """
    api = login()
    targets: list[int]
    with connect() as conn:
        if workout_ids:
            targets = list(workout_ids)
        else:
            cutoff = date.today().isoformat()
            future = (date.today() + timedelta(days=21)).isoformat()
            rows = conn.execute(
                """
                SELECT DISTINCT sw.workout_id
                FROM scheduled_workouts sw
                LEFT JOIN workout_details wd ON wd.workout_id = sw.workout_id
                WHERE sw.workout_id IS NOT NULL
                  AND sw.scheduled_date BETWEEN ? AND ?
                  AND wd.workout_id IS NULL
                LIMIT ?
                """,
                (cutoff, future, limit),
            ).fetchall()
            targets = [r["workout_id"] for r in rows]

    inserted = 0
    failures = 0
    with connect() as conn:
        for wid in targets:
            try:
                data = api.get_workout_by_id(wid)
            except Exception as e:
                log.warning("Workout detail %s falhou: %s", wid, e)
                failures += 1
                continue
            if not data:
                continue
            steps = _flatten_workout_steps(data.get("workoutSegments") or [])
            conn.execute(
                """
                INSERT OR REPLACE INTO workout_details
                (workout_id, name, sport, estimated_duration_s, estimated_distance_m, steps_json, raw)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    int(wid),
                    data.get("workoutName"),
                    (data.get("sportType") or {}).get("sportTypeKey"),
                    int(data["estimatedDurationInSecs"]) if data.get("estimatedDurationInSecs") else None,
                    data.get("estimatedDistanceInMeters"),
                    json.dumps(steps, default=str),
                    json.dumps(data, default=str),
                ),
            )
            inserted += 1

    log.info("Workout details: %d ok, %d falhas", inserted, failures)
    return {"inserted": inserted, "failures": failures}


def _seconds_to_min(seconds: int | float | None) -> int | None:
    if seconds is None:
        return None
    return int(seconds // 60)
