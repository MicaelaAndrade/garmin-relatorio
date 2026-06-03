"""Desempenho do último treino executado — painel de detalhe por atividade.

Reaproveita a análise técnica de natação do coach (_build_swim_tech_analysis) e
adiciona comparação vs prescrito (mesmo esporte na semana) com checagem de
intensidade real por zona de FC. Para corrida/ciclismo monta métricas genéricas
(cadência, Training Effect) já que não há análise técnica per-atividade dedicada.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from ..db import connect
from . import coach
from .zones_distribution import zones_from_raw

SPORT_ICON = {
    "run": "🏃",
    "bike": "🚴",
    "swim": "🏊",
    "yoga": "🧘",
    "strength": "💪",
    "walking": "🚶",
}

_ZONE_ORDER = {"Z1": 1, "Z2": 2, "Z3": 3, "Z4": 4, "Z5": 5}


def _fmt_duration(s: float | int | None) -> str:
    total = int(s or 0)
    h, rem = divmod(total, 3600)
    m = rem // 60
    return f"{h}h{m:02d}min" if h else f"{m}min"


def _zone_bars(raw: dict, fallback: dict | None) -> tuple[list[dict], str | None]:
    """Barras de tempo por zona Z1-Z5. Usa hrTimeInZone do raw; cai pro zones_from_raw."""
    secs = {f"Z{i}": float(raw.get(f"hrTimeInZone_{i}") or 0) for i in range(1, 6)}
    total = sum(secs.values())
    if total <= 0 and fallback:
        secs = {f"Z{i}": float(fallback.get(f"z{i}") or 0) for i in range(1, 6)}
        total = sum(secs.values())
    if total <= 0:
        return [], None
    bars = [
        {"zone": z, "secs": int(v), "pct": round(v / total * 100)}
        for z, v in secs.items()
        if v > 0
    ]
    dominant = max(secs.items(), key=lambda kv: kv[1])[0]
    return bars, dominant


def _is_executed(w: dict) -> bool:
    ex = w.get("executed")
    return bool(ex and ex.get("completed"))


def _match_prescribed(
    sport: str, started_at: str, actual_dist_m: float
) -> tuple[dict | None, str | None, str | None]:
    """Acha o treino prescrito do coach pra esse esporte na semana da atividade.

    Retorna (workout, match_kind, day_label). match_kind ∈ {"exact","shifted",None}:
    exact = prescrito no mesmo dia; shifted = prescrito noutro dia (treino movido).

    No caso shifted (treino antecipado/adiado, como puxar o nado de quinta pra quarta),
    ignora os slots já executados e escolhe o de distância mais próxima da realizada —
    senão casaria com a rodagem leve em vez do intervalado que a atleta de fato fez.
    """
    try:
        d = datetime.fromisoformat(started_at).date()
    except (ValueError, TypeError):
        return None, None, None
    week_start = date.fromordinal(d.toordinal() - d.weekday())
    try:
        sched = coach.coach_schedule(week_start)
    except Exception:
        return None, None, None
    if not sched.get("available"):
        return None, None, None
    day_idx = d.weekday()
    same_sport: list[tuple[int, dict, str]] = []
    for day in sched.get("days", []):
        for w in day.get("workouts", []):
            if w.get("sport") == sport and not w.get("is_race"):
                same_sport.append((day.get("day_idx"), w, day.get("day_label")))
    if not same_sport:
        return None, None, None
    for idx, w, label in same_sport:
        if idx == day_idx:
            return w, "exact", label
    # Slots ainda não executados primeiro; entre eles, distância mais próxima da realizada
    candidates = [t for t in same_sport if not _is_executed(t[1])] or same_sport
    idx, w, label = min(
        candidates,
        key=lambda t: abs((t[1].get("distance_km") or 0) * 1000 - (actual_dist_m or 0)),
    )
    return w, "shifted", label


def _build_comparison(
    sport: str, raw: dict, dist_m: float, prescribed: dict, match_kind: str, day_label: str | None
) -> dict:
    prescribed_dist_m = (prescribed.get("distance_km") or 0) * 1000 or None
    pres_zone = prescribed.get("zone")
    pres_kind = prescribed.get("kind")
    dist_pct = round(dist_m / prescribed_dist_m * 100) if prescribed_dist_m and dist_m else None

    intensity_note = None
    intensity_rating = "neutral"
    if pres_zone and pres_zone in _ZONE_ORDER:
        target = _ZONE_ORDER[pres_zone]
        total = sum(float(raw.get(f"hrTimeInZone_{i}") or 0) for i in range(1, 6))
        if total > 0:
            at_or_above = sum(float(raw.get(f"hrTimeInZone_{i}") or 0) for i in range(target, 6))
            pct_at = round(at_or_above / total * 100)
            dominant = max(
                ((f"Z{i}", float(raw.get(f"hrTimeInZone_{i}") or 0)) for i in range(1, 6)),
                key=lambda kv: kv[1],
            )[0]
            if target >= 4 and pct_at < 15:
                intensity_note = (
                    f"Prescrito {pres_zone} ({pres_kind}), mas só {pct_at}% do tempo em "
                    f"{pres_zone}+ — dominante foi {dominant}. Distância cumprida, "
                    f"mas a intensidade ficou abaixo do prescrito."
                )
                intensity_rating = "warn"
            elif pct_at >= 15:
                intensity_note = f"{pct_at}% do tempo em {pres_zone}+ — pegou a intensidade prescrita."
                intensity_rating = "good"

    return {
        "match_kind": match_kind,
        "day_label": day_label,
        "label": prescribed.get("label"),
        "prescribed_zone": pres_zone,
        "prescribed_kind": pres_kind,
        "prescribed_distance_label": (
            coach._format_distance(sport, prescribed_dist_m) if prescribed_dist_m else None
        ),
        "distance_pct": dist_pct,
        "intensity_note": intensity_note,
        "intensity_rating": intensity_rating,
    }


def _generic_metrics(sport: str, raw: dict) -> list[dict]:
    """Métricas pra corrida/ciclismo (swim usa a análise técnica do coach)."""
    metrics: list[dict] = []
    if sport == "run":
        cad = raw.get("averageRunningCadenceInStepsPerMinute") or raw.get("averageRunCadence")
        if cad:
            rating = "good" if cad >= 170 else "warn"
            hint = "boa cadência" if cad >= 170 else "alvo 170-180 passos/min"
            metrics.append({"name": "Cadência", "value": f"{int(cad)} passos/min", "rating": rating, "hint": hint})
    elif sport == "bike":
        cad = raw.get("averageBikingCadenceInRevPerMinute") or raw.get("averageBikeCadence")
        if cad:
            metrics.append({"name": "Cadência", "value": f"{int(cad)} rpm", "rating": "neutral", "hint": "pedalada"})
        power = raw.get("avgPower") or raw.get("averagePower")
        if power:
            metrics.append({"name": "Potência", "value": f"{int(power)} W", "rating": "neutral", "hint": "média"})
    te_aero = raw.get("aerobicTrainingEffect")
    te_anaero = raw.get("anaerobicTrainingEffect")
    if te_aero is not None or te_anaero is not None:
        parts = []
        if te_aero is not None:
            parts.append(f"aer {float(te_aero):.1f}")
        if te_anaero is not None:
            parts.append(f"ana {float(te_anaero):.1f}")
        label = (raw.get("trainingEffectLabel") or "").lower().replace("_", " ") or "estímulo"
        metrics.append({"name": "Training Effect", "value": " · ".join(parts), "rating": "neutral", "hint": label})
    return metrics


def last_workout() -> dict:
    """Desempenho do treino mais recente. Painel de detalhe por atividade."""
    with connect() as conn:
        r = conn.execute(
            """
            SELECT id, sport, started_at, duration_s, distance_m, avg_hr, max_hr,
                   avg_pace_s_km, avg_speed_kmh, calories, raw
            FROM activities
            ORDER BY started_at DESC
            LIMIT 1
            """
        ).fetchone()
    if not r:
        return {"available": False}

    a = dict(r)
    raw = json.loads(a.get("raw") or "{}")
    sport = a["sport"]
    dist = a["distance_m"] or 0
    dur = a["duration_s"] or 0

    header = {
        "activity_id": a["id"],
        "sport": sport,
        "icon": SPORT_ICON.get(sport, "🏅"),
        "name": raw.get("activityName") or raw.get("name") or "Treino",
        "started_at": a["started_at"],
        "distance_label": coach._format_distance(sport, dist) if dist else None,
        "duration_label": _fmt_duration(dur),
        "calories": int(a["calories"]) if a["calories"] else None,
        "avg_hr": a["avg_hr"],
        "max_hr": a["max_hr"],
        "hr_source": raw.get("_hrSource"),
    }
    if sport == "bike":
        spd = a.get("avg_speed_kmh")
        if not spd and dur and dist:
            spd = round((dist / 1000) / (dur / 3600), 1)
        header["pace_label"] = f"{spd} km/h" if spd else None
    elif a["avg_pace_s_km"]:
        p = float(a["avg_pace_s_km"])
        header["pace_label"] = (
            coach._format_pace_per_100m(p) if sport == "swim" else coach._format_pace_per_km(p)
        )
    else:
        header["pace_label"] = None

    zone_bars, dominant = _zone_bars(raw, zones_from_raw(raw))

    # Comparação vs prescrito do coach (mesmo esporte na semana)
    prescribed, match_kind, day_label = _match_prescribed(sport, a["started_at"], dist)
    comparison = None
    prescribed_dist_m = None
    if prescribed:
        prescribed_dist_m = (prescribed.get("distance_km") or 0) * 1000 or None
        comparison = _build_comparison(sport, raw, dist, prescribed, match_kind, day_label)
        # FC óptica de pulso não funciona embaixo d'água (sinal atrasa/achata picos):
        # a zona da natação é só indicativa, cadência/pace contam mais a real intensidade.
        if (
            sport == "swim"
            and raw.get("_hrSource") in (None, "wrist_optical")
            and comparison.get("intensity_note")
        ):
            comparison["intensity_note"] += (
                " (FC óptica subaquática é imprecisa — confira pela cadência e pace puro também)"
            )

    # Análise técnica: swim reaproveita o coach; demais usam métricas genéricas
    swim_tech = None
    metrics: list[dict] = []
    if sport == "swim":
        exec_data = {
            "raw": raw,
            "duration_s": dur,
            "distance_m": dist,
            "avg_pace_s_km": a["avg_pace_s_km"],
            "avg_hr": a["avg_hr"],
            "calories": a["calories"],
            "started_at": a["started_at"],
        }
        swim_tech = coach._build_swim_tech_analysis(exec_data, prescribed_dist_m)
    else:
        metrics = _generic_metrics(sport, raw)

    return {
        "available": True,
        "header": header,
        "zones": zone_bars,
        "dominant_zone": dominant,
        "swim_tech": swim_tech,
        "metrics": metrics,
        "comparison": comparison,
    }
