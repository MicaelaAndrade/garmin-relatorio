"""Ingest do export GDPR do Garmin (Manage Your Data > Export Your Data).

Le os JSONs de DI_CONNECT/* sem precisar logar. Carrega historico completo.

IMPORTANTE: o export usa unidades diferentes da API live:
- distance: centimetros (nao metros)
- duration: milissegundos (nao segundos)

Ambos sao convertidos pra m/s aqui pra bater com o schema do DB.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import config
from ..db import connect

log = logging.getLogger(__name__)

SPORT_MAP = {
    "running": "run",
    "treadmill_running": "run",
    "trail_running": "run",
    "indoor_running": "run",
    "cycling": "bike",
    "indoor_cycling": "bike",
    "road_biking": "bike",
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


def _extract_cadence(act: dict, sport: str) -> float | None:
    """Export GDPR usa nomes diferentes da API live (avg* vs average*InXxxPerMinute).

    Para corrida: avgRunCadence vem em passos/min POR PERNA (~60-90).
    Convencao do dashboard e' total de passos/min (~160-180), entao dobra.
    avgDoubleCadence ja vem dobrado quando presente.
    """
    if sport == "run":
        cad = act.get("avgDoubleCadence")
        if cad:
            return float(cad)
        cad = act.get("avgRunCadence")
        if cad:
            return round(float(cad) * 2, 1)
        cad = act.get("averageRunningCadenceInStepsPerMinute")
        return float(cad) if cad else None
    if sport == "bike":
        cad = act.get("avgBikeCadence") or act.get("averageBikingCadenceInRevPerMinute")
        return float(cad) if cad else None
    if sport == "swim":
        cad = act.get("avgSwimCadence") or act.get("averageSwimCadenceInStrokesPerMinute")
        return float(cad) if cad else None
    return None


def _extract_speed(act: dict, sport: str) -> float | None:
    """Velocidade em km/h. Bike e walking usam isso em vez de pace.

    Prioriza avgSpeed (m/s) se presente, senao calcula de distancia/duracao.
    """
    if sport not in ("bike", "walking"):
        return None
    avg = act.get("avgSpeed") or act.get("averageSpeed")
    if avg:
        return round(float(avg) * 3.6, 2)
    duration_ms = act.get("duration") or 0
    distance_cm = act.get("distance") or 0
    if duration_ms <= 0 or distance_cm <= 0:
        return None
    distance_km = distance_cm / 100_000.0
    duration_h = duration_ms / 3_600_000.0
    return round(distance_km / duration_h, 2) if duration_h > 0 else None

VO2MAX_SPORT_MAP = {
    "RUNNING": "run",
    "CYCLING": "bike",
    "GENERIC": "run",  # Garmin usa GENERIC pra running quando nao tem cycling power data
}


def _export_dir() -> Path:
    if not config.garmin_export_dir:
        raise RuntimeError(
            "GARMIN_EXPORT_DIR nao configurado no .env. "
            "Aponte para a pasta DI_CONNECT do export."
        )
    if not config.garmin_export_dir.is_dir():
        raise RuntimeError(f"Diretorio nao existe: {config.garmin_export_dir}")
    return config.garmin_export_dir


def _ms_to_s(ms: float | int | None) -> int | None:
    return int(ms / 1000) if ms else None


def _cm_to_m(cm: float | int | None) -> float | None:
    return float(cm) / 100.0 if cm else None


def _epoch_ms_to_iso(ms: float | int | None) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000).isoformat()


def ingest_activities() -> dict[str, int]:
    """Le summarizedActivities*.json (todos os arquivos numerados)."""
    fitness = _export_dir() / "DI-Connect-Fitness"
    files = sorted(fitness.glob("*_summarizedActivities.json"))
    if not files:
        log.warning("Nenhum summarizedActivities encontrado em %s", fitness)
        return {"inserted": 0, "updated": 0}

    inserted = updated = 0
    with connect() as conn:
        for f in files:
            data = json.loads(f.read_text())
            # Estrutura: [{"summarizedActivitiesExport": [...]}]
            for chunk in data:
                for act in chunk.get("summarizedActivitiesExport", []):
                    activity_type = act.get("activityType") or ""
                    sport = SPORT_MAP.get(activity_type.lower(), "other")

                    duration_s = _ms_to_s(act.get("duration")) or 0
                    distance_m = _cm_to_m(act.get("distance"))
                    pace = (
                        duration_s / (distance_m / 1000.0)
                        if distance_m and distance_m > 100 and sport != "bike"
                        else None
                    )
                    elev = act.get("elevationGain")
                    elev_m = _cm_to_m(elev) if elev else None  # elevationGain tambem em cm

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
                            training_load=excluded.training_load
                        """,
                        (
                            "garmin",
                            str(act["activityId"]),
                            sport,
                            _epoch_ms_to_iso(act.get("startTimeLocal") or act.get("beginTimestamp")),
                            duration_s,
                            distance_m,
                            int(act["avgHr"]) if act.get("avgHr") else None,
                            int(act["maxHr"]) if act.get("maxHr") else None,
                            pace,
                            _extract_speed(act, sport),
                            _extract_cadence(act, sport),
                            elev_m,
                            int(act["calories"]) if act.get("calories") else None,
                            act.get("activityTrainingLoad"),
                            json.dumps(act, default=str),
                        ),
                    )
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        updated += 1

    log.info("Activities (export): %d inseridas, %d atualizadas", inserted, updated)
    return {"inserted": inserted, "updated": updated}


def ingest_sleep() -> dict[str, int]:
    """Le todos os *_sleepData.json em DI-Connect-Wellness."""
    wellness = _export_dir() / "DI-Connect-Wellness"
    files = sorted(wellness.glob("*_sleepData.json"))
    inserted = 0
    with connect() as conn:
        for f in files:
            for night in json.loads(f.read_text()):
                date_str = night.get("calendarDate")
                if not date_str:
                    continue
                deep = night.get("deepSleepSeconds") or 0
                light = night.get("lightSleepSeconds") or 0
                rem = night.get("remSleepSeconds") or 0  # pode nao existir no export
                awake = night.get("awakeSleepSeconds") or 0
                total = deep + light + rem  # total sem awake
                score = (night.get("sleepScores") or {}).get("overallScore")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sleep
                    (date, total_min, deep_min, light_min, rem_min, awake_min, score, raw)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        date_str,
                        int(total // 60) if total else None,
                        int(deep // 60) if deep else None,
                        int(light // 60) if light else None,
                        int(rem // 60) if rem else None,
                        int(awake // 60) if awake else None,
                        int(score) if score else None,
                        json.dumps(night, default=str),
                    ),
                )
                inserted += 1
    log.info("Sleep (export): %d noites", inserted)
    return {"inserted": inserted}


def ingest_daily_metrics() -> dict[str, int]:
    """Combina UDSFile (resting HR, body battery, stress, steps) com healthStatusData (HRV)."""
    aggregator = _export_dir() / "DI-Connect-Aggregator"
    wellness = _export_dir() / "DI-Connect-Wellness"

    # 1. Carrega healthStatusData -> dict[date] -> {hrv, hr, spo2}
    health: dict[str, dict[str, Any]] = {}
    for f in sorted(wellness.glob("*_healthStatusData.json")):
        for day in json.loads(f.read_text()):
            d = day.get("calendarDate")
            if not d:
                continue
            metrics = {}
            for m in day.get("metrics", []):
                metrics[m["type"]] = m.get("value")
            health[d] = metrics

    # 2. Itera UDSFile e merge com health
    inserted = 0
    with connect() as conn:
        for f in sorted(aggregator.glob("UDSFile_*.json")):
            for day in json.loads(f.read_text()):
                d = day.get("calendarDate")
                if not d:
                    continue
                health_metrics = health.get(d, {})
                stress_obj = day.get("allDayStress") or {}
                bb = day.get("bodyBatteryDynamicFeedbackEvent") or {}

                conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_metrics
                    (date, resting_hr, hrv_overnight, body_battery, stress_avg, steps, raw)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        d,
                        day.get("restingHeartRate"),
                        health_metrics.get("HRV"),
                        bb.get("endOfDayValue") or bb.get("dailyMaxBodyBattery"),
                        stress_obj.get("averageStressLevel") or stress_obj.get("avgStressLevel"),
                        day.get("totalSteps"),
                        json.dumps(
                            {"uds": day, "health": health_metrics}, default=str
                        ),
                    ),
                )
                inserted += 1
    log.info("Daily metrics (export): %d dias", inserted)
    return {"inserted": inserted}


def ingest_vo2max() -> dict[str, int]:
    metrics = _export_dir() / "DI-Connect-Metrics"
    files = sorted(metrics.glob("MetricsMaxMetData_*.json"))
    inserted = 0
    with connect() as conn:
        for f in files:
            for entry in json.loads(f.read_text()):
                date_str = entry.get("calendarDate")
                value = entry.get("vo2MaxValue")
                sport_raw = entry.get("sport") or "GENERIC"
                if not date_str or value is None:
                    continue
                sport = VO2MAX_SPORT_MAP.get(sport_raw, "run")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO vo2max (date, sport, value, raw)
                    VALUES (?,?,?,?)
                    """,
                    (date_str, sport, float(value), json.dumps(entry, default=str)),
                )
                inserted += 1
    log.info("VO2max (export): %d entries", inserted)
    return {"inserted": inserted}


def ingest_race_predictions() -> dict[str, int]:
    """Predicoes de corrida que o proprio Garmin calcula (FirstBeat, baseado em VO2max)."""
    metrics = _export_dir() / "DI-Connect-Metrics"
    files = sorted(metrics.glob("RunRacePredictions_*.json"))
    inserted = 0
    with connect() as conn:
        for f in files:
            for entry in json.loads(f.read_text()):
                date_str = entry.get("calendarDate")
                if not date_str:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO race_predictions
                    (date, race_5k_s, race_10k_s, race_half_s, race_marathon_s, raw)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (
                        date_str,
                        entry.get("raceTime5K"),
                        entry.get("raceTime10K"),
                        entry.get("raceTimeHalf"),
                        entry.get("raceTimeMarathon"),
                        json.dumps(entry, default=str),
                    ),
                )
                inserted += 1
    log.info("Race predictions (export): %d entries", inserted)
    return {"inserted": inserted}


def ingest_hr_zones() -> dict[str, int]:
    """Le 75928777_heartRateZones.json — zonas calibradas pelo Garmin."""
    wellness = _export_dir() / "DI-Connect-Wellness"
    files = list(wellness.glob("*_heartRateZones.json"))
    if not files:
        return {"inserted": 0}
    inserted = 0
    with connect() as conn:
        for f in files:
            zones = json.loads(f.read_text())
            for z in zones:
                sport = (z.get("sport") or "DEFAULT").lower()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO hr_zones
                    (sport, resting_hr, max_hr, z1_floor, z2_floor, z3_floor,
                     z4_floor, z5_floor, method, raw)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        sport,
                        z.get("restingHeartRateUsed"),
                        z.get("maxHeartRateUsed"),
                        z.get("zone1Floor"),
                        z.get("zone2Floor"),
                        z.get("zone3Floor"),
                        z.get("zone4Floor"),
                        z.get("zone5Floor"),
                        z.get("trainingMethod"),
                        json.dumps(z, default=str),
                    ),
                )
                inserted += 1
    log.info("HR zones (export): %d", inserted)
    return {"inserted": inserted}


def ingest_personal_records() -> dict[str, int]:
    fitness = _export_dir() / "DI-Connect-Fitness"
    files = list(fitness.glob("*_personalRecord.json"))
    if not files:
        return {"inserted": 0}
    inserted = 0
    with connect() as conn:
        for f in files:
            data = json.loads(f.read_text())
            for chunk in data:
                for pr in chunk.get("personalRecords", []):
                    pr_id = pr.get("personalRecordId")
                    if not pr_id:
                        continue
                    achieved = pr.get("prStartTimeGMT") or pr.get("createdDate") or ""
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO personal_records
                        (pr_id, activity_id, record_type, value, achieved_at, is_current, raw)
                        VALUES (?,?,?,?,?,?,?)
                        """,
                        (
                            int(pr_id),
                            str(pr.get("activityId") or ""),
                            pr.get("personalRecordType") or "",
                            float(pr.get("value") or 0),
                            achieved,
                            1 if pr.get("current") else 0,
                            json.dumps(pr, default=str),
                        ),
                    )
                    inserted += 1
    log.info("PRs (export): %d", inserted)
    return {"inserted": inserted}


def ingest_menstrual_cycles() -> dict[str, int]:
    """Le MenstrualCycles.json e DailyMenstrualLogs.json (sensiveis — armazenado local)."""
    wellness = _export_dir() / "DI-Connect-Wellness"
    cycles_files = list(wellness.glob("*_MenstrualCycles.json"))
    logs_files = list(wellness.glob("*_DailyMenstrualLogs.json"))

    cycles_inserted = logs_inserted = 0
    with connect() as conn:
        for f in cycles_files:
            for c in json.loads(f.read_text()):
                start = c.get("startDate")
                if not start:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO menstrual_cycles
                    (start_date, predicted_cycle_length, predicted_period_length,
                     actual_cycle_length, actual_period_length, cycle_type,
                     fertile_window_start, fertile_window_length, status, raw)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        start,
                        c.get("predictedCycleLength"),
                        c.get("predictedPeriodLength"),
                        c.get("actualCycleLength"),
                        c.get("actualPeriodLength"),
                        c.get("cycleType"),
                        c.get("fertileWindowStart"),
                        c.get("fertileWindowLength"),
                        c.get("status"),
                        json.dumps(c, default=str),
                    ),
                )
                cycles_inserted += 1

        for f in logs_files:
            for log_entry in json.loads(f.read_text()):
                d = log_entry.get("calendarDate")
                if not d:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO menstrual_logs
                    (date, flow, symptoms, moods, ovulation_day, raw)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (
                        d,
                        log_entry.get("flow"),
                        json.dumps(log_entry.get("symptoms") or []),
                        json.dumps(log_entry.get("moods") or []),
                        1 if log_entry.get("ovulationDay") else 0,
                        json.dumps(log_entry, default=str),
                    ),
                )
                logs_inserted += 1

    log.info("Cycles: %d / Logs: %d", cycles_inserted, logs_inserted)
    return {"cycles": cycles_inserted, "logs": logs_inserted}


def ingest_all() -> dict[str, dict[str, int]]:
    return {
        "activities": ingest_activities(),
        "sleep": ingest_sleep(),
        "daily_metrics": ingest_daily_metrics(),
        "vo2max": ingest_vo2max(),
        "race_predictions": ingest_race_predictions(),
        "hr_zones": ingest_hr_zones(),
        "personal_records": ingest_personal_records(),
        "menstrual": ingest_menstrual_cycles(),
    }
