"""Schedule prescrito pelo coach (via Treius/parceiros Garmin Connect).

Le scheduled_workouts ingerido por garmin.ingest_scheduled_workouts e organiza
em formato compativel com TrainingPlanDay (mesmo schema que o heuristico).

Quando workout_details (estrutura/steps) esta disponivel, agrupa blocos
consecutivos para mostrar resumo legivel (ex: "6×20s @ 5:33/km com 30s rec").

Multiplas sessoes no mesmo dia (ex: bike + nado) sao preservadas como uma lista
agrupada por dia.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from ..db import connect


# Step types que sao Z1-Z2 por convencao (warmup, cooldown, recovery em pace.zone baixo)
LOW_STEP_TYPES = {"warmup", "cooldown", "recovery", "rest"}
# Step types "main set" — zona depende do target
MAIN_STEP_TYPES = {"interval", "other", "active"}


def _pace_ms_to_pace_per_km(ms: float | None) -> str | None:
    """Pace em m/s -> string mm:ss/km."""
    if not ms or ms <= 0:
        return None
    s_per_km = 1000.0 / ms
    m = int(s_per_km // 60)
    s = int(s_per_km % 60)
    return f"{m}:{s:02d}/km"


def _format_end(step: dict) -> str:
    cond = step.get("end_condition")
    val = step.get("end_value") or 0
    if cond == "time":
        v = int(val)
        if v >= 60:
            m, s = divmod(v, 60)
            return f"{m}min" if s == 0 else f"{m}:{s:02d}"
        return f"{v}s"
    if cond == "distance":
        v = float(val)
        return f"{v/1000:.1f}km" if v >= 1000 else f"{int(v)}m"
    return "lap"


def _step_zone(step: dict, sport: str) -> str | None:
    """Estima zona do step (Z1..Z5 ou label livre)."""
    target = step.get("target_type")
    step_type = step.get("step_type")
    if target == "heart.rate.zone" and step.get("zone_number"):
        return f"Z{step['zone_number']}"
    if step_type in LOW_STEP_TYPES:
        return "Z2" if step_type in ("warmup", "cooldown") else "Z1"
    if target == "pace.zone" and step.get("target_value_one"):
        # heuristica: ms > 3.5 (corrida ~ 4:45/km) e' rapido (Z4); 2.5-3.5 e' Z3; <2.5 Z2
        ms = (step.get("target_value_one") or 0)
        ms2 = (step.get("target_value_two") or ms)
        avg_ms = (ms + ms2) / 2
        if sport == "swim":
            return "Z3" if avg_ms > 1.3 else "Z2"
        if sport == "bike":
            return "Z4" if avg_ms > 9 else ("Z3" if avg_ms > 7 else "Z2")
        # run
        if avg_ms >= 3.5:
            return "Z4"
        if avg_ms >= 2.8:
            return "Z3"
        return "Z2"
    return None


def _zone_bucket(zone: str | None) -> str:
    """Mapeia 'Z1'..'Z5' pra 'low'|'mid'|'high'."""
    if not zone:
        return "low"
    if zone in ("Z1", "Z2"):
        return "low"
    if zone == "Z3":
        return "mid"
    return "high"  # Z4, Z5, Race


def _build_fueling(
    sport: str,
    duration_s: int | None,
    distance_m: float | None,
    blocks: list[dict] | None,
) -> dict | None:
    """Hidratação + carbo + sódio sugeridos pra um treino prescrito.

    Mesma lógica do race day, mas considera a duração prescrita.
    """
    if not duration_s or duration_s < 1200:  # < 20min nao precisa nada
        return None

    duration_h = duration_s / 3600

    # Pace medio se temos distancia
    pace_alvo_s_km = None
    if distance_m and distance_m > 0 and sport in ("run", "swim"):
        pace_alvo_s_km = int(duration_s / (distance_m / 1000))

    # Velocidade media bike
    speed_alvo_kmh = None
    if distance_m and distance_m > 0 and sport == "bike":
        speed_alvo_kmh = round(distance_m / 1000 / duration_h, 1)

    # Hidratacao
    fluid_ml_per_h = 600
    fluid_total_ml = int(fluid_ml_per_h * duration_h)

    # Carbo
    if duration_h < 1:
        carbs_g_per_h = 0
        carbs_msg = "Treino curto — só água."
    elif duration_h < 2.5:
        carbs_g_per_h = 45
        carbs_msg = "Repor a partir de 45min — gel ou sport drink."
    else:
        carbs_g_per_h = 75
        carbs_msg = "Repor desde o início — múltiplas fontes."
    carbs_total_g = int(carbs_g_per_h * duration_h)

    # Sodio
    sodium_mg_per_h = 500 if duration_h > 1.5 else 300

    return {
        "duration_label": f"{int(duration_s // 60)}min",
        "pace_alvo_s_km": pace_alvo_s_km,
        "speed_alvo_kmh": speed_alvo_kmh,
        "fluid_ml_per_h": fluid_ml_per_h,
        "fluid_total_ml": fluid_total_ml,
        "carbs_g_per_h": carbs_g_per_h,
        "carbs_total_g": carbs_total_g,
        "carbs_message": carbs_msg,
        "sodium_mg_per_h": sodium_mg_per_h,
    }


def _build_execution(
    executions: list[dict] | None,
    prescribed_dur_s: int | None,
    prescribed_dist_m: float | None,
    prescribed_blocks: list[dict],
) -> dict | None:
    """Compara prescrito × executado. Retorna None se nao houve execucao.

    Score baseado em (1) duracao cumprida (% do prescrito), (2) distancia (se aplicavel).
    """
    if not executions:
        return None
    # Pega a execucao mais recente (caso tenha duplicatas)
    exec_data = max(executions, key=lambda e: e.get("started_at") or "")
    actual_dur = exec_data["duration_s"] or 0
    actual_dist = exec_data["distance_m"] or 0
    actual_pace = exec_data["avg_pace_s_km"]
    actual_hr = exec_data["avg_hr"]

    duration_pct = None
    if prescribed_dur_s and prescribed_dur_s > 0:
        duration_pct = round(actual_dur / prescribed_dur_s * 100)

    distance_pct = None
    if prescribed_dist_m and prescribed_dist_m > 0:
        distance_pct = round(actual_dist / prescribed_dist_m * 100)

    # Score geral: completou se >=80% da duracao prescrita
    completion_pct = duration_pct if duration_pct is not None else (
        distance_pct if distance_pct is not None else None
    )
    if completion_pct is None:
        status = "executado"
        status_label = "Executado"
    elif completion_pct >= 95:
        status = "completo"
        status_label = "Completo"
    elif completion_pct >= 80:
        status = "quase"
        status_label = "Quase completo"
    elif completion_pct >= 50:
        status = "parcial"
        status_label = "Parcial"
    else:
        status = "iniciado"
        status_label = "Apenas iniciado"

    # Detalhes pace/HR
    notes: list[str] = []
    if actual_dur and prescribed_dur_s:
        diff_min = (actual_dur - prescribed_dur_s) / 60
        if abs(diff_min) > 1:
            notes.append(
                f"Duração: {round(actual_dur/60)}min ({duration_pct}% do prescrito, {'+' if diff_min > 0 else ''}{round(diff_min)}min)"
            )
        else:
            notes.append(f"Duração: {round(actual_dur/60)}min (igual ao prescrito)")
    if actual_dist and prescribed_dist_m:
        notes.append(f"Distância: {actual_dist/1000:.2f}km (prescrito ~{prescribed_dist_m/1000:.2f}km, {distance_pct}%)")
    elif actual_dist:
        notes.append(f"Distância: {actual_dist/1000:.2f}km")
    if actual_pace:
        m, s = divmod(int(actual_pace), 60)
        notes.append(f"Pace médio: {m}:{s:02d}/km")
    if actual_hr:
        notes.append(f"FC média: {int(actual_hr)} bpm")
    if exec_data.get("calories"):
        notes.append(f"Gasto: {int(exec_data['calories'])} kcal")

    return {
        "completed": True,
        "status": status,
        "status_label": status_label,
        "completion_pct": completion_pct,
        "activity_id": exec_data["activity_id"],
        "external_id": exec_data["external_id"],
        "source": exec_data["source"],
        "actual_duration_s": actual_dur,
        "actual_distance_m": actual_dist,
        "actual_pace_s_km": int(actual_pace) if actual_pace else None,
        "actual_avg_hr": int(actual_hr) if actual_hr else None,
        "actual_calories": int(exec_data["calories"]) if exec_data.get("calories") else None,
        "started_at": exec_data["started_at"],
        "notes": notes,
    }


def _step_to_block(step: dict, sport: str) -> dict:
    zone = _step_zone(step, sport)
    pace = (
        _pace_ms_to_pace_per_km(step.get("target_value_one"))
        if step.get("target_type") == "pace.zone"
        else None
    )
    return {
        "block_type": "step",
        "kind": step.get("step_type"),
        "end_label": _format_end(step),
        "duration_s": int(step.get("end_value") or 0) if step.get("end_condition") == "time" else 0,
        "zone": zone,
        "pace": pace,
        "description": step.get("description"),
    }


def _summarize_steps(nodes: list[dict], sport: str) -> list[dict]:
    """Processa lista de nodos (step/repeat) em blocos legiveis.

    Repeats viram um nodo de bloco com `children` e `count`. Steps consecutivos
    identicos fora de repeats sao colapsados (count=N).
    """
    if not nodes:
        return []

    result: list[dict] = []
    for node in nodes:
        if node.get("node_type") == "repeat":
            children = _summarize_steps(node.get("children") or [], sport)
            result.append({
                "block_type": "repeat",
                "count": int(node.get("iterations") or 1),
                "children": children,
                "duration_s": sum(
                    (c.get("duration_s") or 0) * (c.get("count") or 1)
                    for c in children
                ) * int(node.get("iterations") or 1),
            })
            continue
        block = _step_to_block(node, sport)
        # Colapsa steps consecutivos identicos (raro fora de repeats)
        if (
            result
            and result[-1].get("block_type") == "step"
            and (result[-1]["kind"], result[-1]["end_label"], result[-1]["zone"], result[-1]["pace"])
            == (block["kind"], block["end_label"], block["zone"], block["pace"])
        ):
            result[-1]["count"] = (result[-1].get("count") or 1) + 1
            continue
        block["count"] = 1
        result.append(block)
    return result


def _structured_zone_split(steps: list[dict], sport: str) -> tuple[float, float, float, int]:
    """Soma duracoes (em segundos) por bucket (low/mid/high) e total."""
    low = mid = high = 0.0
    total = 0
    for s in steps:
        if s.get("end_condition") != "time":
            continue
        dur = float(s.get("end_value") or 0)
        if dur <= 0:
            continue
        bucket = _zone_bucket(_step_zone(s, sport))
        if bucket == "low":
            low += dur
        elif bucket == "mid":
            mid += dur
        else:
            high += dur
        total += int(dur)
    return low, mid, high, total


# TRIMP por minuto em cada zona (Banister-style). Mesma escala usada em hr_zones.trimp_for_activity.
TRIMP_FACTOR_BY_ZONE = {
    "Z1": 0.9,
    "Z2": 1.5,
    "Z3": 2.5,
    "Z4": 3.5,
    "Z5": 4.5,
}
# TRIMP por minuto quando so' conhecemos o tipo (sem estrutura)
TRIMP_FACTOR_BY_KIND = {
    "intervals": 2.4,
    "fartlek":   2.1,
    "tempo":     2.2,
    "long":      1.7,
    "easy":      1.4,
    "tech":      1.3,
    "race":      3.0,
    "workout":   1.8,
}


# Distribuicao tipica por zonas (Z1-Z2 low, Z3 mid, Z4-Z5 high) por tipo de treino.
# Soma 1.0 em cada linha. Usado pra estimar a distribuicao da semana prescrita.
INTENSITY_BY_KIND = {
    "intervals": (0.20, 0.10, 0.70),  # warmup + main set alto
    "fartlek":   (0.30, 0.30, 0.40),
    "tempo":     (0.30, 0.60, 0.10),
    "long":      (0.85, 0.15, 0.00),
    "easy":      (1.00, 0.00, 0.00),
    "tech":      (1.00, 0.00, 0.00),
    "race":      (0.10, 0.20, 0.70),
    "workout":   (0.60, 0.30, 0.10),  # fallback se nao classificou
}


SPORT_MAP = {
    "running": "run",
    "treadmill_running": "run",
    "trail_running": "run",
    "cycling": "bike",
    "indoor_cycling": "bike",
    "road_biking": "bike",
    "mountain_biking": "bike",
    "lap_swimming": "swim",
    "open_water_swimming": "swim",
    "swimming": "swim",
    "strength_training": "strength",
    "yoga": "yoga",
    "walking": "walking",
}
SPORT_ICON = {"run": "🏃", "bike": "🚴", "swim": "🏊", "strength": "💪", "yoga": "🧘", "walking": "🚶"}
DAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _classify_kind(title: str) -> tuple[str, str | None]:
    """Detecta tipo de treino pelo titulo. Devolve (kind, zone_hint)."""
    t = title.lower()
    if "intervalad" in t or "interval" in t or "tiro" in t:
        return "intervals", "Z4"
    if "fartlek" in t:
        return "fartlek", "Z3-Z4"
    if "tempo" in t or "limiar" in t or "threshold" in t:
        return "tempo", "Z3"
    if "long" in t or "rodag" in t and ("long" in t or "1h" in t or "2h" in t):
        return "long", "Z2"
    if "rodag" in t or "regener" in t or "rec " in t or "leve" in t:
        return "easy", "Z2"
    if "tecn" in t or "drill" in t:
        return "tech", "Z2"
    if "prova" in t or "race" in t or "corrida " in t and "km" in t:
        return "race", "Race"
    return "workout", None


def coach_schedule(start: date | None = None) -> dict[str, Any]:
    """Schedule prescrito pelo coach.

    Default: semana corrente (Seg atual -> Dom atual). Se essa semana ja terminou
    completamente (nada mais a fazer), avanca pra proxima. Coach tipicamente
    cadastra semana a semana, entao priorizar a corrente cobre o caso comum.
    """
    if start is None:
        today = date.today()
        current_monday = today - timedelta(days=today.weekday())
        next_monday = current_monday + timedelta(days=7)
        # Se ja eh domingo e nao tem mais o que treinar essa semana, mostra a proxima
        # (heuristica simples: se hoje >= sex e nao tem treino apos sex, vai pro proximo)
        start = current_monday
        with connect() as conn:
            future_this_week = conn.execute(
                "SELECT COUNT(*) FROM scheduled_workouts WHERE scheduled_date >= ?",
                (today.isoformat(),),
            ).fetchone()[0]
            future_next_week = conn.execute(
                "SELECT COUNT(*) FROM scheduled_workouts WHERE scheduled_date >= ? AND scheduled_date < ?",
                (next_monday.isoformat(), (next_monday + timedelta(days=7)).isoformat()),
            ).fetchone()[0]
        if future_this_week == 0 and future_next_week > 0:
            start = next_monday
    end = start + timedelta(days=6)

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT sw.scheduled_date, sw.sport_type, sw.title, sw.duration_s,
                   sw.distance_m, sw.is_race, sw.workout_id,
                   wd.estimated_duration_s, wd.estimated_distance_m, wd.steps_json
            FROM scheduled_workouts sw
            LEFT JOIN workout_details wd ON wd.workout_id = sw.workout_id
            WHERE sw.scheduled_date >= ? AND sw.scheduled_date <= ?
            ORDER BY sw.scheduled_date
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()

        # Mapa de workouts executados (workoutId no raw da activity)
        executed_map: dict[int, list[dict[str, Any]]] = {}
        act_rows = conn.execute(
            """
            SELECT id, source, external_id, sport, started_at, duration_s, distance_m,
                   avg_hr, max_hr, avg_pace_s_km, calories, raw
            FROM activities
            WHERE started_at >= ?
            """,
            (start.isoformat(),),
        ).fetchall()
        for ar in act_rows:
            try:
                raw = json.loads(ar["raw"] or "{}")
                wid = raw.get("workoutId")
                if wid:
                    executed_map.setdefault(int(wid), []).append({
                        "activity_id": ar["id"],
                        "external_id": ar["external_id"],
                        "source": ar["source"],
                        "sport": ar["sport"],
                        "started_at": ar["started_at"],
                        "duration_s": ar["duration_s"],
                        "distance_m": ar["distance_m"],
                        "avg_hr": ar["avg_hr"],
                        "max_hr": ar["max_hr"],
                        "avg_pace_s_km": ar["avg_pace_s_km"],
                        "calories": ar["calories"],
                        "raw": raw,
                    })
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

    by_day: dict[int, list[dict[str, Any]]] = {i: [] for i in range(7)}
    for r in rows:
        d = date.fromisoformat(r["scheduled_date"])
        idx = (d - start).days
        if idx < 0 or idx > 6:
            continue
        sport = SPORT_MAP.get((r["sport_type"] or "").lower(), "other")
        kind, zone = _classify_kind(r["title"] or "")
        if r["is_race"]:
            kind = "race"
            zone = "Race"
        dur_s = r["estimated_duration_s"] or r["duration_s"]
        dist_m = r["estimated_distance_m"] or r["distance_m"]
        blocks: list[dict[str, Any]] = []
        if r["steps_json"]:
            try:
                steps = json.loads(r["steps_json"])
                blocks = _summarize_steps(steps, sport)
            except json.JSONDecodeError:
                blocks = []
        wid = r["workout_id"]
        prescribed_dist_m = r["estimated_distance_m"] or r["distance_m"]
        executed = _build_execution(executed_map.get(int(wid)) if wid else None, dur_s, prescribed_dist_m, blocks)
        fueling = _build_fueling(sport, dur_s, prescribed_dist_m, blocks)
        by_day[idx].append({
            "sport": sport,
            "icon": SPORT_ICON.get(sport, "•"),
            "kind": kind,
            "label": r["title"],
            "duration_min": round(dur_s / 60) if dur_s else 0,
            "distance_km": round(prescribed_dist_m / 1000, 1) if prescribed_dist_m else None,
            "zone": zone,
            "target": None,
            "is_race": bool(r["is_race"]),
            "blocks": blocks,
            "has_structure": bool(blocks),
            "executed": executed,
            "fueling": fueling,
        })

    days: list[dict[str, Any]] = []
    has_any = False
    for i in range(7):
        items = by_day[i]
        if items:
            has_any = True
        days.append({
            "day_idx": i,
            "day_label": DAY_LABELS[i],
            "workouts": items,
        })

    return {
        "week_start": start.isoformat(),
        "available": has_any,
        "days": days,
        "intensity_mix": _intensity_mix(days),
        "totals": _totals(days),
        "load_comparison": _load_comparison(days),
    }


def _block_trimp(blocks: list[dict], multiplier: int = 1) -> float:
    """TRIMP estimado somando duracao_min * fator por zona, recursivamente."""
    total = 0.0
    for b in blocks:
        if b.get("block_type") == "repeat":
            total += _block_trimp(b.get("children") or [], multiplier * (b.get("count") or 1))
            continue
        dur_s = float(b.get("duration_s") or 0) * (b.get("count") or 1) * multiplier
        if dur_s <= 0:
            continue
        zone = b.get("zone") or "Z2"
        factor = TRIMP_FACTOR_BY_ZONE.get(zone, TRIMP_FACTOR_BY_ZONE["Z2"])
        total += (dur_s / 60.0) * factor
    return total


def _workout_trimp(workout: dict) -> float:
    """TRIMP de 1 workout prescrito. Usa estrutura quando disponivel."""
    if workout.get("blocks"):
        return _block_trimp(workout["blocks"])
    dur_min = workout.get("duration_min") or 0
    factor = TRIMP_FACTOR_BY_KIND.get(workout["kind"], TRIMP_FACTOR_BY_KIND["workout"])
    return float(dur_min) * factor


def _last_week_trimp() -> float:
    """TRIMP real da semana fechada anterior (Seg passada -> Dom passado)."""
    from . import acwr  # import tardio pra evitar ciclo

    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    series = acwr.acwr_series(days=21)
    total = 0.0
    for s in series:
        d = date.fromisoformat(s["day"])
        if last_monday <= d <= last_sunday:
            total += float(s.get("load") or 0)
    return total


def _load_comparison(days_list: list[dict]) -> dict[str, Any]:
    prescribed = 0.0
    for d in days_list:
        for w in d["workouts"]:
            prescribed += _workout_trimp(w)
    last = _last_week_trimp()
    pct = round(prescribed / last * 100) if last > 0 else None
    message = ""
    if pct is None:
        message = "Sem semana passada pra comparar."
    elif pct > 130:
        message = f"Coach prescreveu {pct}% — spike forte vs semana passada. Atenção à carga."
    elif pct > 110:
        message = f"Coach prescreveu {pct}% — progressão moderada."
    elif pct >= 85:
        message = f"Coach prescreveu {pct}% — carga similar à semana passada."
    elif pct >= 60:
        message = f"Coach prescreveu {pct}% — semana mais leve."
    else:
        message = f"Coach prescreveu {pct}% — descanso/taper."
    return {
        "prescribed_trimp": round(prescribed, 1),
        "last_week_trimp": round(last, 1),
        "pct_of_last_week": pct,
        "message": message,
    }


def _accumulate_blocks(blocks: list[dict], multiplier: int = 1) -> tuple[float, float, float]:
    """Soma duracao em cada bucket recursivamente, respeitando repeats."""
    low = mid = high = 0.0
    for b in blocks:
        if b.get("block_type") == "repeat":
            cl, cm, ch = _accumulate_blocks(b.get("children") or [], multiplier * (b.get("count") or 1))
            low += cl
            mid += cm
            high += ch
            continue
        dur = float(b.get("duration_s") or 0) * (b.get("count") or 1) * multiplier
        if dur <= 0:
            continue
        bucket = _zone_bucket(b.get("zone"))
        if bucket == "low":
            low += dur
        elif bucket == "mid":
            mid += dur
        else:
            high += dur
    return low, mid, high


def _intensity_mix(days: list[dict[str, Any]]) -> dict[str, int]:
    """Calcula % Z1-Z2 / Z3 / Z4-Z5 da semana prescrita.

    Quando ha estrutura, soma duracao real por zona detectada (respeitando repeats).
    Quando nao ha, fallback heuristico por tipo (INTENSITY_BY_KIND ponderado por duracao).
    """
    low = mid = high = 0.0
    for d in days:
        for w in d["workouts"]:
            if w.get("blocks"):
                cl, cm, ch = _accumulate_blocks(w["blocks"])
                low += cl
                mid += cm
                high += ch
                continue
            weight = max(float(w.get("duration_min") or 0) * 60, 60)
            ratios = INTENSITY_BY_KIND.get(w["kind"], INTENSITY_BY_KIND["workout"])
            low += weight * ratios[0]
            mid += weight * ratios[1]
            high += weight * ratios[2]
    total = low + mid + high
    if total <= 0:
        return {"low": 0, "mid": 0, "high": 0}
    low_pct = round(low / total * 100)
    mid_pct = round(mid / total * 100)
    high_pct = 100 - low_pct - mid_pct
    return {"low": low_pct, "mid": mid_pct, "high": high_pct}


def _totals(days: list[dict[str, Any]]) -> dict[str, Any]:
    sessions = 0
    duration_min = 0.0
    distance_km = 0.0
    by_sport: dict[str, int] = {}
    for d in days:
        for w in d["workouts"]:
            sessions += 1
            duration_min += w.get("duration_min") or 0
            distance_km += w.get("distance_km") or 0
            by_sport[w["sport"]] = by_sport.get(w["sport"], 0) + 1
    return {
        "sessions": sessions,
        "duration_min": round(duration_min, 0),
        "distance_km": round(distance_km, 1),
        "by_sport": by_sport,
    }


def coach_today() -> dict[str, Any]:
    """Workouts prescritos para hoje (atalho usado por widget compacto)."""
    today = date.today()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT sw.workout_id, sw.sport_type, sw.title, sw.duration_s, sw.distance_m, sw.is_race,
                   wd.estimated_duration_s, wd.steps_json, wd.estimated_distance_m
            FROM scheduled_workouts sw
            LEFT JOIN workout_details wd ON wd.workout_id = sw.workout_id
            WHERE sw.scheduled_date = ?
            ORDER BY sw.id
            """,
            (today.isoformat(),),
        ).fetchall()

        # Mapa de execucoes pra hoje
        executed_map: dict[int, list[dict[str, Any]]] = {}
        act_rows = conn.execute(
            """
            SELECT id, source, external_id, sport, started_at, duration_s, distance_m,
                   avg_hr, max_hr, avg_pace_s_km, calories, raw
            FROM activities
            WHERE started_at LIKE ?
            """,
            (f"{today.isoformat()}%",),
        ).fetchall()
        for ar in act_rows:
            try:
                raw = json.loads(ar["raw"] or "{}")
                wid = raw.get("workoutId")
                if wid:
                    executed_map.setdefault(int(wid), []).append({
                        "activity_id": ar["id"], "external_id": ar["external_id"], "source": ar["source"],
                        "sport": ar["sport"], "started_at": ar["started_at"],
                        "duration_s": ar["duration_s"], "distance_m": ar["distance_m"],
                        "avg_hr": ar["avg_hr"], "max_hr": ar["max_hr"],
                        "avg_pace_s_km": ar["avg_pace_s_km"], "calories": ar["calories"], "raw": raw,
                    })
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
    items = []
    for r in rows:
        sport = SPORT_MAP.get((r["sport_type"] or "").lower(), "other")
        kind, zone = _classify_kind(r["title"] or "")
        if r["is_race"]:
            kind = "race"
            zone = "Race"
        dur_s = r["estimated_duration_s"] or r["duration_s"]
        blocks: list[dict[str, Any]] = []
        if r["steps_json"]:
            try:
                steps = json.loads(r["steps_json"])
                blocks = _summarize_steps(steps, sport)
            except json.JSONDecodeError:
                blocks = []
        wid = r["workout_id"]
        prescribed_dist_m = r["estimated_distance_m"] or r["distance_m"]
        executed = _build_execution(
            executed_map.get(int(wid)) if wid else None,
            dur_s, prescribed_dist_m, blocks,
        )
        fueling = _build_fueling(sport, dur_s, prescribed_dist_m, blocks)
        items.append({
            "sport": sport,
            "icon": SPORT_ICON.get(sport, "•"),
            "kind": kind,
            "label": r["title"],
            "duration_min": round(dur_s / 60) if dur_s else 0,
            "distance_km": round(prescribed_dist_m / 1000, 1) if prescribed_dist_m else None,
            "zone": zone,
            "is_race": bool(r["is_race"]),
            "blocks": blocks,
            "has_structure": bool(blocks),
            "executed": executed,
            "fueling": fueling,
        })
    return {"date": today.isoformat(), "workouts": items}
