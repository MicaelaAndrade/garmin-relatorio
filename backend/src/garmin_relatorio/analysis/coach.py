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
    if target == "heart.rate.zone":
        if step.get("zone_number"):
            return f"Z{step['zone_number']}"
        # Sem zone_number: classifica pelo BPM usando as zonas reais do usuário.
        # Pra range (134-140bpm), usa a ponta alta — fica conservador.
        bpm = step.get("target_value_two") or step.get("target_value_one")
        if bpm:
            from .hr_zones import zone_for_hr
            z = zone_for_hr(float(bpm))
            if z >= 1:
                return f"Z{z}"
        # fallback por step_type
        if step_type in LOW_STEP_TYPES:
            return "Z2" if step_type in ("warmup", "cooldown") else "Z1"
        return None
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


# Bandas de SWOLF pra piscina 25m (mulher iniciante/intermediaria). SWOLF abaixo
# de 36 ja' eh territorio de nadadora avancada. Acima de 50, ha bastante coisa pra
# trabalhar (deslize curto + ou tempo por length alto).
SWOLF_BANDS = [
    (36, "ótimo", "good"),
    (42, "bom", "good"),
    (50, "banda iniciante", "warn"),
    (999, "muito alto", "bad"),
]


def _swolf_band(swolf: float) -> tuple[str, str]:
    for threshold, label, rating in SWOLF_BANDS:
        if swolf < threshold:
            return label, rating
    return "muito alto", "bad"


def _build_swim_tech_analysis(exec_data: dict, prescribed_dist_m: float | None) -> dict | None:
    """Análise técnica de natação (DPS, SWOLF, cadência, pace puro, parada).

    Devolve {metrics: [...], tips: [...], checklist: [...]}. None se faltam dados.
    """
    raw = exec_data.get("raw") or {}
    actual_dur = exec_data["duration_s"] or 0
    actual_dist = exec_data["distance_m"] or 0
    if actual_dist <= 0:
        return None

    metrics: list[dict] = []
    tips: list[str] = []

    # Pool length em metros (raw vem em cm pelo GDPR, em m pela live API).
    pool_raw = raw.get("poolLength") or 0
    pool_m = pool_raw / 100 if pool_raw >= 50 else pool_raw

    # DPS — distance per stroke, em m/braçada. Precisa de avgStrokes por length.
    avg_strokes_per_length = raw.get("avgStrokes")
    dps: float | None = None
    if avg_strokes_per_length and pool_m:
        dps = pool_m / float(avg_strokes_per_length)
        if dps >= 2.0:
            rating, hint = "good", "deslize longo"
        elif dps >= 1.7:
            rating, hint = "good", "bom deslize"
        elif dps >= 1.4:
            rating, hint = "warn", "alongue a braçada (alcance + rotação)"
        else:
            rating, hint = "bad", "DPS baixo — foque em puxada longa"
        metrics.append({
            "name": "DPS",
            "value": f"{dps:.2f} m/braçada",
            "rating": rating,
            "hint": hint,
        })

    # SWOLF
    swolf = raw.get("averageSwolf")
    if swolf:
        label, rating = _swolf_band(float(swolf))
        target_hint = "alvo 38" if float(swolf) >= 42 else None
        hint = label if not target_hint else f"{label} ({target_hint})"
        metrics.append({
            "name": "SWOLF",
            "value": str(int(swolf)),
            "rating": rating,
            "hint": hint,
        })

    # Cadência (stroke rate)
    cad = raw.get("averageSwimCadenceInStrokesPerMinute")
    if cad:
        if cad >= 32:
            rating, hint = "good", "boa pra séries hard"
        elif cad >= 28:
            rating, hint = "good", "ok pra base"
        elif cad >= 24:
            rating, hint = "warn", "subir pra 30+ em séries fortes"
        else:
            rating, hint = "warn", "muito lenta — perde ritmo"
        metrics.append({
            "name": "Cadência",
            "value": f"{int(cad)} strokes/min",
            "rating": rating,
            "hint": hint,
        })

    # Pace puro (sem descansos) usando movingDuration
    moving_dur = raw.get("movingDuration")
    if moving_dur and actual_dist:
        pace_pure_s_km = moving_dur / (actual_dist / 1000)
        metrics.append({
            "name": "Pace puro",
            "value": _format_pace_per_100m(pace_pure_s_km),
            "rating": "neutral",
            "hint": "descontando descansos",
        })

    # Parada total (duration - movingDuration)
    if moving_dur and actual_dur:
        stopped_s = max(0, int(actual_dur - moving_dur))
        if stopped_s > 60:
            stopped_min = stopped_s / 60
            # Avalia se a parada eh esperada (serie) ou excessiva
            stopped_pct = stopped_s / actual_dur
            if stopped_pct > 0.4:
                rating, hint = "warn", "muita parada — série ou cansaço?"
            elif stopped_pct > 0.15:
                rating, hint = "neutral", "normal pra série"
            else:
                rating, hint = "good", "fluido"
            metrics.append({
                "name": "Parada total",
                "value": f"{stopped_min:.0f}min",
                "rating": rating,
                "hint": hint,
            })

    # Melhor 100m da sessão — referencia capacidade vs ritmo médio de série
    fastest_100 = raw.get("fastestSplit_100")
    if fastest_100 and fastest_100 > 0:
        m, s = divmod(int(round(fastest_100)), 60)
        metrics.append({
            "name": "Melhor 100m",
            "value": f"{m}:{s:02d}",
            "rating": "neutral",
            "hint": "split mais rápido da sessão",
        })

    # Lengths ativos (piscina) — separa volume técnico de descanso/splits
    active_lengths = raw.get("activeLengths")
    if active_lengths and pool_m:
        expected = int(actual_dist / pool_m) if pool_m else None
        hint = "lengths nadados"
        if expected and active_lengths < expected * 0.9:
            hint = f"{int(active_lengths)} de ~{expected} esperados — alguns lengths não foram detectados"
        metrics.append({
            "name": "Lengths",
            "value": str(int(active_lengths)),
            "rating": "neutral",
            "hint": hint,
        })

    # Training Effect (aeróbico / anaeróbico) — sai do device
    te_aero = raw.get("aerobicTrainingEffect")
    te_anaero = raw.get("anaerobicTrainingEffect")
    if te_aero is not None or te_anaero is not None:
        parts = []
        if te_aero is not None:
            parts.append(f"aer {float(te_aero):.1f}")
        if te_anaero is not None:
            parts.append(f"ana {float(te_anaero):.1f}")
        te_label = (raw.get("trainingEffectLabel") or "").lower().replace("_", " ") or "estímulo"
        metrics.append({
            "name": "Training Effect",
            "value": " · ".join(parts),
            "rating": "neutral",
            "hint": te_label,
        })

    # Distribuição em zonas de FC — soma os segundos por zona e mostra zona dominante
    zone_secs = {
        f"Z{i}": float(raw.get(f"hrTimeInZone_{i}") or 0) for i in range(1, 6)
    }
    total_z = sum(zone_secs.values())
    if total_z > 60:
        dominant = max(zone_secs.items(), key=lambda kv: kv[1])
        dom_pct = int(round(dominant[1] / total_z * 100))
        z45_pct = int(round((zone_secs["Z4"] + zone_secs["Z5"]) / total_z * 100))
        hint = f"dominante {dominant[0]} ({dom_pct}%)"
        if z45_pct > 0:
            hint += f" · Z4-5 {z45_pct}%"
        rating = "good" if dominant[0] in ("Z2", "Z3") else "neutral"
        metrics.append({
            "name": "Zonas FC",
            "value": f"{dominant[0]} {dom_pct}%",
            "rating": rating,
            "hint": hint,
        })

    # Tips heurísticas (max 4)
    if swolf and float(swolf) >= 42:
        tips.append(
            "Reduzir SWOLF (alvo 38): drill 6-3-6 (1 length só braço D, 1 só braço E) força o lado fraco e simetriza a puxada"
        )
    if cad and float(cad) < 28:
        tips.append(f"Cadência {int(cad)} strokes/min é baixa — em série forte mire 30+ (respirar 2/2 ajuda a manter ritmo)")
    if dps and dps < 1.7:
        tips.append("DPS abaixo de 1.7m — trabalhar alcance e rotação de quadril pra puxada mais longa")
    if prescribed_dist_m and actual_dist < prescribed_dist_m * 0.7:
        tips.append(f"Faltou {(prescribed_dist_m - actual_dist):.0f}m do prescrito — repor na próxima ou conversar com o coach")
    # Respiração unilateral direita é o padrão atual — Garmin não detecta lado, só lembra de destravar o esquerdo
    tips.append("Respiração: 200m de aquecimento em 3/3 bilateral pra destravar o lado esquerdo (Garmin não detecta o lado)")

    return {
        "metrics": metrics,
        "tips": tips[:4],
        "checklist": [
            "Aquecimento com 200m respirando 3/3 bilateral (destravar lado esquerdo)",
            "Em série forte, mudei pra 2/2 alternando lados (mantém cadência)",
            "Drill 6-3-6 ou catch-up unilateral pra simetrizar a puxada",
            "Kick constante saindo do quadril (não só dos joelhos)",
            "Cabeça alinhada — olhar pro fundo, não pra frente",
            "Empurrei a água até atrás da coxa (puxada completa)",
        ],
    }


def _sum_steps_distance_m(nodes: list[dict]) -> float:
    """Soma metros dos steps com end_condition='distance', respeitando iterations dos repeats.

    Usado pra natação: o estimatedDistanceInMeters do Garmin infla o prescrito (soma
    paradas como se fossem distância). Calcular pela soma dos steps reflete o que o
    coach efetivamente escreveu no Treinus.
    """
    total = 0.0
    for n in nodes or []:
        if n.get("node_type") == "repeat":
            it = int(n.get("iterations") or 1)
            total += it * _sum_steps_distance_m(n.get("children") or [])
        elif n.get("node_type") == "step":
            if n.get("end_condition") == "distance":
                total += float(n.get("end_value") or 0)
    return total


def _format_pace_per_km(s_per_km: float) -> str:
    m, s = divmod(int(round(s_per_km)), 60)
    return f"{m}:{s:02d}/km"


def _format_pace_per_100m(s_per_km: float) -> str:
    s_per_100 = s_per_km / 10.0
    m, s = divmod(int(round(s_per_100)), 60)
    return f"{m}:{s:02d}/100m"


def _format_distance(sport: str, distance_m: float) -> str:
    if sport == "swim":
        return f"{int(round(distance_m))}m"
    return f"{distance_m/1000:.2f}km"


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

    # Pace medio se temos distancia (run em /km, swim em /100m)
    pace_alvo_s_km: int | None = None
    pace_alvo_label: str | None = None
    if distance_m and distance_m > 0 and sport in ("run", "swim"):
        pace_alvo_s_km = int(duration_s / (distance_m / 1000))
        pace_alvo_label = (
            _format_pace_per_100m(pace_alvo_s_km)
            if sport == "swim"
            else _format_pace_per_km(pace_alvo_s_km)
        )

    # Velocidade media bike
    speed_alvo_kmh: float | None = None
    speed_alvo_label: str | None = None
    if distance_m and distance_m > 0 and sport == "bike":
        speed_alvo_kmh = round(distance_m / 1000 / duration_h, 1)
        speed_alvo_label = f"{speed_alvo_kmh} km/h"

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
        "pace_alvo_label": pace_alvo_label,
        "speed_alvo_kmh": speed_alvo_kmh,
        "speed_alvo_label": speed_alvo_label,
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
    sport: str = "run",
) -> dict | None:
    """Compara prescrito × executado. Retorna None se nao houve execucao.

    Score baseado em (1) duracao cumprida (% do prescrito), (2) distancia (se aplicavel).
    Para swim/bike, a distancia tende a ser mais confiavel que duracao (recovery entre
    series infla o tempo total) — entao quando ha prescricao de distancia, usa ela.
    """
    if not executions:
        return None
    # Pega a execucao mais recente (caso tenha duplicatas)
    exec_data = max(executions, key=lambda e: e.get("started_at") or "")
    actual_dur = exec_data["duration_s"] or 0
    actual_dist = exec_data["distance_m"] or 0
    actual_pace = exec_data["avg_pace_s_km"]
    actual_speed = exec_data.get("avg_speed_kmh")
    actual_hr = exec_data["avg_hr"]
    raw = exec_data.get("raw") or {}

    duration_pct = None
    if prescribed_dur_s and prescribed_dur_s > 0:
        duration_pct = round(actual_dur / prescribed_dur_s * 100)

    distance_pct = None
    if prescribed_dist_m and prescribed_dist_m > 0:
        distance_pct = round(actual_dist / prescribed_dist_m * 100)

    # Pra swim/bike, distancia eh referencia primaria quando disponivel
    if sport in ("swim", "bike") and distance_pct is not None:
        completion_pct = distance_pct
    elif duration_pct is not None:
        completion_pct = duration_pct
    else:
        completion_pct = distance_pct
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
    elif actual_dur:
        notes.append(f"Duração: {round(actual_dur/60)}min")

    if actual_dist and prescribed_dist_m:
        notes.append(
            f"Distância: {_format_distance(sport, actual_dist)} "
            f"(prescrito ~{_format_distance(sport, prescribed_dist_m)}, {distance_pct}%)"
        )
    elif actual_dist:
        notes.append(f"Distância: {_format_distance(sport, actual_dist)}")

    # Metrica primaria de ritmo: pace pra run/swim, velocidade pra bike
    if sport == "bike":
        # Prefere avg_speed_kmh; senao computa a partir de dist/dur
        speed_kmh = actual_speed
        if not speed_kmh and actual_dur and actual_dist:
            speed_kmh = round((actual_dist / 1000) / (actual_dur / 3600), 1)
        if speed_kmh:
            notes.append(f"Velocidade média: {speed_kmh} km/h")
    elif sport == "swim" and actual_pace:
        notes.append(f"Pace médio: {_format_pace_per_100m(float(actual_pace))}")
    elif actual_pace:
        notes.append(f"Pace médio: {_format_pace_per_km(float(actual_pace))}")

    if actual_hr:
        notes.append(f"FC média: {int(actual_hr)} bpm")

    # Extras sport-aware extraidos do raw da activity
    if sport == "swim":
        swolf = raw.get("averageSwolf")
        if swolf:
            notes.append(f"SWOLF médio: {int(swolf)}")
        strokes = raw.get("strokes") or raw.get("totalStrokes")
        if strokes:
            notes.append(f"Braçadas: {int(strokes)}")
        cad = raw.get("averageSwimCadenceInStrokesPerMinute")
        if cad:
            notes.append(f"Cadência: {int(cad)} braçadas/min")
        pool = raw.get("poolLength")
        if pool:
            # poolLength em cm pelos exports GDPR; live API ja vem em m
            pool_m = pool / 100 if pool >= 50 else pool
            notes.append(f"Piscina: {int(pool_m)}m")
    elif sport == "bike":
        cad = (
            raw.get("averageBikingCadenceInRevPerMinute")
            or raw.get("averageBikeCadence")
        )
        if cad:
            notes.append(f"Cadência: {int(cad)} rpm")
        if raw.get("avgPower") or raw.get("averagePower"):
            notes.append(f"Potência média: {int(raw.get('avgPower') or raw.get('averagePower'))} W")
    else:  # run
        cad = (
            raw.get("averageRunningCadenceInStepsPerMinute")
            or raw.get("averageRunCadence")
        )
        if cad:
            notes.append(f"Cadência: {int(cad)} passos/min")

    if exec_data.get("calories"):
        notes.append(f"Gasto: {int(exec_data['calories'])} kcal")

    swim_tech = _build_swim_tech_analysis(exec_data, prescribed_dist_m) if sport == "swim" else None

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
        "actual_speed_kmh": float(actual_speed) if actual_speed else None,
        "actual_avg_hr": int(actual_hr) if actual_hr else None,
        "actual_calories": int(exec_data["calories"]) if exec_data.get("calories") else None,
        "started_at": exec_data["started_at"],
        "notes": notes,
        "swim_tech": swim_tech,
    }


def _format_hr_target(v1: float | None, v2: float | None) -> str | None:
    if not v1:
        return None
    a = int(round(v1))
    b = int(round(v2)) if v2 else a
    return f"{a}bpm" if a == b else f"{a}-{b}bpm"


def _step_to_block(step: dict, sport: str) -> dict:
    zone = _step_zone(step, sport)
    target = step.get("target_type")
    pace: str | None = None
    if target == "pace.zone":
        ms = step.get("target_value_one")
        if ms and ms > 0:
            s_per_km = 1000.0 / ms
            if sport == "swim":
                pace = _format_pace_per_100m(s_per_km)
            else:
                pace = _pace_ms_to_pace_per_km(ms)
    hr_target = (
        _format_hr_target(step.get("target_value_one"), step.get("target_value_two"))
        if target == "heart.rate.zone"
        else None
    )
    end_cond = step.get("end_condition")
    end_val = float(step.get("end_value") or 0)
    duration_s = 0
    if end_cond == "time":
        duration_s = int(end_val)
    elif end_cond == "distance" and end_val > 0:
        # Estima duração pra step prescrito em distância (comum em natação).
        # Usa pace alvo se houver; senão pace típico por sport.
        pace_ms = step.get("target_value_one") if target == "pace.zone" else None
        if not pace_ms or pace_ms <= 0:
            # Fallback: pace típico por sport (m/s)
            pace_ms = {"swim": 0.83, "run": 3.0, "bike": 8.3}.get(sport, 2.5)
        duration_s = int(end_val / float(pace_ms))
    return {
        "block_type": "step",
        "kind": step.get("step_type"),
        "end_label": _format_end(step),
        "duration_s": duration_s,
        "zone": zone,
        "pace": pace,
        "hr_target": hr_target,
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


def _build_execution_indices(
    conn,
    start_iso: str,
    end_iso: str | None = None,
) -> tuple[dict[int, list[dict[str, Any]]], dict[tuple[str, str], list[dict[str, Any]]]]:
    """Carrega atividades do periodo e separa em dois indices:

    - executed_map[workout_id] : matching exato pelo workoutId no raw
    - unclaimed_by_day_sport[(YYYY-MM-DD, sport)] : fallback pra atividades
      sem workoutId (caso comum em natacao/bike). Cada (dia, sport) eh uma lista
      ordenada por started_at; itens sao "drenados" via _claim_fallback.
    """
    executed_map: dict[int, list[dict[str, Any]]] = {}
    unclaimed: dict[tuple[str, str], list[dict[str, Any]]] = {}

    if end_iso is None:
        query = (
            "SELECT id, source, external_id, sport, started_at, duration_s, distance_m, "
            "avg_hr, max_hr, avg_pace_s_km, avg_speed_kmh, calories, raw "
            "FROM activities WHERE started_at >= ? ORDER BY started_at"
        )
        params: tuple[str, ...] = (start_iso,)
    else:
        query = (
            "SELECT id, source, external_id, sport, started_at, duration_s, distance_m, "
            "avg_hr, max_hr, avg_pace_s_km, avg_speed_kmh, calories, raw "
            "FROM activities WHERE started_at >= ? AND started_at < ? ORDER BY started_at"
        )
        params = (start_iso, end_iso)

    for ar in conn.execute(query, params).fetchall():
        try:
            raw = json.loads(ar["raw"] or "{}")
        except (json.JSONDecodeError, ValueError, TypeError):
            raw = {}
        entry = {
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
            "avg_speed_kmh": ar["avg_speed_kmh"],
            "calories": ar["calories"],
            "raw": raw,
        }
        wid = raw.get("workoutId")
        if wid:
            executed_map.setdefault(int(wid), []).append(entry)
            continue
        day = (ar["started_at"] or "")[:10]
        if not day or not ar["sport"]:
            continue
        unclaimed.setdefault((day, ar["sport"]), []).append(entry)
    return executed_map, unclaimed


def _claim_fallback(
    unclaimed: dict[tuple[str, str], list[dict[str, Any]]],
    scheduled_date: str,
    sport: str,
    prescribed_dur_s: int | None,
    prescribed_dist_m: float | None,
) -> list[dict[str, Any]] | None:
    """Drena a atividade que melhor encaixa no treino prescrito.

    Melhor encaixe = menor diferenca de distancia (se ha prescricao), depois
    duracao. Se nao ha referencia, pega o primeiro disponivel. A atividade eh
    removida do indice pra evitar dupla atribuicao quando ha 2 treinos do mesmo
    esporte no mesmo dia.
    """
    key = (scheduled_date, sport)
    bucket = unclaimed.get(key)
    if not bucket:
        return None

    def score(entry: dict[str, Any]) -> tuple[int, float]:
        # Distancia tem peso maior pra swim/bike; tempo pra run/strength/etc.
        if prescribed_dist_m and prescribed_dist_m > 0 and entry["distance_m"]:
            return (0, abs(entry["distance_m"] - prescribed_dist_m))
        if prescribed_dur_s and prescribed_dur_s > 0 and entry["duration_s"]:
            return (1, abs(entry["duration_s"] - prescribed_dur_s))
        return (2, 0.0)

    bucket.sort(key=score)
    chosen = bucket.pop(0)
    return [chosen]


def _load_strength_routines_by_weekday(conn) -> dict[int, dict[str, Any]]:
    """Mapeia weekday (0=Seg..6=Dom) -> rotina de fortalecimento mais recente.

    O coach prescreve fortalecimento via app Treius (não publica no calendário
    Garmin), então puxamos de `strength_routines` (ingest do MFit). Pega o maior
    `id` por weekday quando há múltiplas — assume que a mais recente é a ativa.
    """
    rows = conn.execute(
        """
        SELECT r.id, r.name, r.weekday, r.routine_label,
               (SELECT COUNT(*) FROM strength_exercises e WHERE e.routine_id = r.id) AS exercise_count
        FROM strength_routines r
        WHERE r.weekday IS NOT NULL
        ORDER BY r.weekday, r.id DESC
        """
    ).fetchall()
    by_weekday: dict[int, dict[str, Any]] = {}
    for r in rows:
        wd = int(r["weekday"])
        if wd in by_weekday:
            continue
        by_weekday[wd] = {
            "routine_id": r["id"],
            "name": r["name"],
            "routine_label": r["routine_label"],
            "exercise_count": r["exercise_count"],
        }
    return by_weekday


def _strength_executed(conn, day_iso: str) -> dict[str, Any] | None:
    """Detecta se houve atividade strength_training no dia (Garmin marca pelo relógio)."""
    row = conn.execute(
        """
        SELECT id, source, external_id, started_at, duration_s, avg_hr, max_hr, calories
        FROM activities
        WHERE sport = 'strength' AND date(started_at) = ?
        ORDER BY started_at
        LIMIT 1
        """,
        (day_iso,),
    ).fetchone()
    if not row:
        return None
    notes: list[str] = []
    if row["duration_s"]:
        notes.append(f"Duração: {round(row['duration_s']/60)}min")
    if row["avg_hr"]:
        notes.append(f"FC média: {int(row['avg_hr'])} bpm")
    if row["calories"]:
        notes.append(f"Gasto: {int(row['calories'])} kcal")
    return {
        "completed": True,
        "status": "executado",
        "status_label": "Executado",
        "completion_pct": None,
        "activity_id": row["id"],
        "external_id": row["external_id"],
        "source": row["source"],
        "actual_duration_s": row["duration_s"] or 0,
        "actual_distance_m": 0,
        "actual_pace_s_km": None,
        "actual_speed_kmh": None,
        "actual_avg_hr": int(row["avg_hr"]) if row["avg_hr"] else None,
        "actual_calories": int(row["calories"]) if row["calories"] else None,
        "started_at": row["started_at"],
        "notes": notes,
        "swim_tech": None,
    }


def _build_strength_workout(routine: dict[str, Any], executed: dict[str, Any] | None) -> dict[str, Any]:
    label = f"Fortalecimento — {routine['name']}" if routine.get("name") else "Fortalecimento"
    return {
        "sport": "strength",
        "icon": SPORT_ICON["strength"],
        "kind": "strength",
        "label": label,
        "routine_id": routine["routine_id"],
        "routine_label": routine.get("routine_label"),
        "exercise_count": routine.get("exercise_count"),
        "duration_min": 0,
        "distance_km": None,
        "zone": None,
        "target": None,
        "is_race": False,
        "blocks": [],
        "has_structure": False,
        "executed": executed,
        "fueling": None,
    }


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

        executed_map, unclaimed_by_day_sport = _build_execution_indices(
            conn, start.isoformat(), end_iso=(end + timedelta(days=1)).isoformat()
        )
        strength_by_weekday = _load_strength_routines_by_weekday(conn)
        strength_execs = {
            wd: _strength_executed(conn, (start + timedelta(days=wd)).isoformat())
            for wd in strength_by_weekday
        }

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
        steps: list[dict] = []
        if r["steps_json"]:
            try:
                steps = json.loads(r["steps_json"])
                blocks = _summarize_steps(steps, sport)
            except json.JSONDecodeError:
                blocks = []
        wid = r["workout_id"]
        prescribed_dist_m = r["estimated_distance_m"] or r["distance_m"]
        # Swim: soma dos steps (end_condition=distance) reflete melhor o que o coach
        # escreveu — o estimatedDistanceInMeters do Garmin infla por causa de paradas.
        if sport == "swim" and steps:
            steps_dist = _sum_steps_distance_m(steps)
            if steps_dist > 0:
                prescribed_dist_m = steps_dist
        execs = executed_map.get(int(wid)) if wid else None
        if not execs:
            execs = _claim_fallback(
                unclaimed_by_day_sport, r["scheduled_date"], sport,
                dur_s, prescribed_dist_m,
            )
        executed = _build_execution(execs, dur_s, prescribed_dist_m, blocks, sport)
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

    # Injeta fortalecimento por weekday (coach prescreve via Treius, não no Garmin)
    for wd, routine in strength_by_weekday.items():
        if any(w["sport"] == "strength" for w in by_day[wd]):
            continue
        by_day[wd].append(_build_strength_workout(routine, strength_execs.get(wd)))

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

        executed_map, unclaimed_by_day_sport = _build_execution_indices(
            conn, today.isoformat(), (today + timedelta(days=1)).isoformat()
        )
        strength_by_weekday = _load_strength_routines_by_weekday(conn)
        strength_today = strength_by_weekday.get(today.weekday())
        strength_exec_today = (
            _strength_executed(conn, today.isoformat()) if strength_today else None
        )
    items = []
    for r in rows:
        sport = SPORT_MAP.get((r["sport_type"] or "").lower(), "other")
        kind, zone = _classify_kind(r["title"] or "")
        if r["is_race"]:
            kind = "race"
            zone = "Race"
        dur_s = r["estimated_duration_s"] or r["duration_s"]
        blocks: list[dict[str, Any]] = []
        steps: list[dict] = []
        if r["steps_json"]:
            try:
                steps = json.loads(r["steps_json"])
                blocks = _summarize_steps(steps, sport)
            except json.JSONDecodeError:
                blocks = []
        wid = r["workout_id"]
        prescribed_dist_m = r["estimated_distance_m"] or r["distance_m"]
        if sport == "swim" and steps:
            steps_dist = _sum_steps_distance_m(steps)
            if steps_dist > 0:
                prescribed_dist_m = steps_dist
        execs = executed_map.get(int(wid)) if wid else None
        if not execs:
            execs = _claim_fallback(
                unclaimed_by_day_sport, today.isoformat(), sport,
                dur_s, prescribed_dist_m,
            )
        executed = _build_execution(execs, dur_s, prescribed_dist_m, blocks, sport)
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
    if strength_today and not any(w["sport"] == "strength" for w in items):
        items.append(_build_strength_workout(strength_today, strength_exec_today))
    return {"date": today.isoformat(), "workouts": items}
