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
        garmin = _garmin_prediction_for(r)
        riegel = _riegel_prediction_for(r)
        out.append({
            **dict(r),
            "days_to": days_to,
            "weeks_to": weeks_to,
            "phase": phase,
            "phase_message": _phase_message(phase, weeks_to),
            "garmin_prediction": garmin,
            "riegel_prediction": riegel,
            "fueling": _fueling_for(r, garmin, riegel),
            "readiness": _readiness_for(r, days_to, phase),
        })
    return out


def _readiness_for(race_row, days_to: int, phase: str) -> dict | None:
    """Race readiness score 0-100 baseado em ACWR, overtraining, taper, sono, VO2max trend.

    Componentes:
    - ACWR (peso 25): ideal 0.8-1.3
    - Overtraining (peso 25): score 0/4 = 100, 4/4 = 0
    - Taper compliance (peso 20): em taper, ATL deve estar caindo
    - Sono 7d (peso 15): media >=7h = 100; <6h = 0
    - VO2max trend 30d (peso 15): subindo = 100; estável = 70; caindo = 40
    """
    if days_to < 0:
        return None  # prova ja' passou

    from . import acwr as acwr_mod, overtraining, performance_mgmt
    from ..db import connect
    from datetime import timedelta as _td

    components: list[dict] = []
    score = 0.0
    total_weight = 0.0

    # 1. ACWR
    acwr_status = acwr_mod.current_status()
    acwr_val = acwr_status.get("acwr")
    if acwr_val is not None:
        if 0.8 <= acwr_val <= 1.3:
            sub_score = 100
            note = "Sweet spot"
        elif 1.3 < acwr_val <= 1.5:
            sub_score = 70
            note = "Moderado"
        elif acwr_val > 1.5:
            sub_score = 30
            note = "Alto risco"
        elif acwr_val < 0.8:
            sub_score = 60
            note = "Pode estar destreinada"
        else:
            sub_score = 50
            note = "Indefinido"
        score += sub_score * 0.25
        total_weight += 0.25
        components.append({"name": "ACWR", "score": sub_score, "weight": 25, "value": acwr_val, "note": note})

    # 2. Overtraining (inverso)
    overt = overtraining.overtraining_score()
    overt_score_max = overt.get("max_score", 4)
    overt_val = overt.get("score", 0)
    ot_inv_score = round((1 - overt_val / overt_score_max) * 100) if overt_score_max else 100
    score += ot_inv_score * 0.25
    total_weight += 0.25
    components.append({
        "name": "Overtraining",
        "score": ot_inv_score,
        "weight": 25,
        "value": f"{overt_val}/{overt_score_max}",
        "note": overt.get("flag"),
    })

    # 3. Taper compliance (so' relevante se em peak/taper/race_week)
    pmc = performance_mgmt.performance_management(days=42)
    if pmc.get("available"):
        tsb_now = pmc["current"]["tsb"]
        if phase in ("taper", "race_week"):
            # TSB deve estar positivo no taper
            if tsb_now > 5:
                taper_score = 100
                note = "TSB positivo, fresca"
            elif tsb_now > -5:
                taper_score = 70
                note = "TSB neutro, ok"
            else:
                taper_score = 40
                note = "Ainda fadigada"
        elif phase == "peak":
            # No peak, TSB ainda pode estar negativo mas perto de 0
            if -15 <= tsb_now <= 10:
                taper_score = 90
                note = "Balanço peak ok"
            else:
                taper_score = 60
                note = "Balanço fora do esperado"
        else:
            # Base/build: TSB nao tao crítico, mas evitar < -25
            if tsb_now > -10:
                taper_score = 90
                note = "Balanço produtivo"
            elif tsb_now > -25:
                taper_score = 70
                note = "Carga alta"
            else:
                taper_score = 40
                note = "Sobrecarregada"
        score += taper_score * 0.20
        total_weight += 0.20
        components.append({"name": "Taper/Form", "score": taper_score, "weight": 20, "value": f"TSB {tsb_now:+.1f}", "note": note})

    # 4. Sono 7d
    with connect() as conn:
        sleep_rows = conn.execute(
            "SELECT total_min FROM sleep WHERE date >= date('now', '-7 days') AND total_min IS NOT NULL"
        ).fetchall()
    if sleep_rows:
        avg_sleep_min = sum(r["total_min"] for r in sleep_rows) / len(sleep_rows)
        avg_sleep_h = avg_sleep_min / 60
        if avg_sleep_h >= 7.5:
            sleep_score = 100
            note = "Sono ideal"
        elif avg_sleep_h >= 7:
            sleep_score = 85
            note = "Sono bom"
        elif avg_sleep_h >= 6:
            sleep_score = 60
            note = "Sono regular"
        else:
            sleep_score = 30
            note = "Sono curto"
        score += sleep_score * 0.15
        total_weight += 0.15
        components.append({
            "name": "Sono 7d",
            "score": sleep_score,
            "weight": 15,
            "value": f"{avg_sleep_h:.1f}h/noite",
            "note": note,
        })

    # 5. VO2max trend (30d)
    with connect() as conn:
        vo2_rows = conn.execute(
            "SELECT vo2max_running FROM biometrics WHERE vo2max_running IS NOT NULL AND date >= date('now', '-30 days') ORDER BY date"
        ).fetchall()
    if len(vo2_rows) >= 5:
        first_vo2 = float(vo2_rows[0]["vo2max_running"])
        last_vo2 = float(vo2_rows[-1]["vo2max_running"])
        delta = last_vo2 - first_vo2
        if delta > 0.5:
            vo2_score = 100
            note = "Subindo"
        elif delta >= -0.5:
            vo2_score = 80
            note = "Estável"
        else:
            vo2_score = 50
            note = "Caindo"
        score += vo2_score * 0.15
        total_weight += 0.15
        components.append({
            "name": "VO2max 30d",
            "score": vo2_score,
            "weight": 15,
            "value": f"{last_vo2:.1f} ({delta:+.1f})",
            "note": note,
        })

    if total_weight == 0:
        return None
    final_score = round(score / total_weight)

    # Status final
    if final_score >= 85:
        status = "pronta"
        status_message = "Pronta pra dar o melhor. Faz a prova."
    elif final_score >= 70:
        status = "boa"
        status_message = "Em boa forma. Pequenos ajustes ajudam."
    elif final_score >= 55:
        status = "regular"
        status_message = "Forma regular. Foque na recuperação dos próximos dias."
    else:
        status = "precaucao"
        status_message = "Precisa cuidar. Considera revisar a prova ou os próximos dias."

    return {
        "score": final_score,
        "status": status,
        "status_message": status_message,
        "components": components,
    }


def _riegel_prediction_for(race_row) -> dict | None:
    """Predicao por formula de Riegel (T2 = T1 * (D2/D1)^1.06).

    Usa a melhor referencia recente (60d) da mesma modalidade.
    """
    sport = race_row["sport"]
    if sport not in ("run", "swim"):
        return None
    dist = race_row["distance_m"]
    if not dist:
        return None

    from . import performance
    pred = performance.predict_race(sport)
    if not pred or not pred.get("reference") or not pred.get("predictions"):
        return None
    ref = pred["reference"]
    # Acha a predicao mais proxima da distancia alvo
    closest = min(
        pred["predictions"], key=lambda p: abs(p["distance_m"] - dist)
    )
    diff_pct = abs(closest["distance_m"] - dist) / dist * 100
    if diff_pct > 40:
        return None
    return {
        "predicted_time_s": closest["predicted_time_s"],
        "predicted_pace_s_km": closest["predicted_pace_s_km"],
        "confidence": closest.get("confidence"),
        "based_on": {
            "distance_m": ref["distance_m"],
            "duration_s": ref["duration_s"],
            "started_at": ref["started_at"],
        },
    }


def _fueling_for(race_row, garmin_pred: dict | None, riegel_pred: dict | None) -> dict | None:
    """Sugestao de hidratacao + carbs baseado em duracao estimada da prova.

    Regras gerais (atletas amadores, clima moderado):
    - Hidratacao: 500-750 ml/h (mais em clima quente)
    - Carbs: nada se < 60min; 30-60 g/h se 60-150min; 60-90 g/h se > 150min
    - Sodio: 300-700 mg/h em provas longas
    """
    sport = race_row["sport"]
    distance_m = race_row["distance_m"] or 0
    # Usa Garmin se disponivel, senao Riegel, senao estimativa por modalidade
    est_seconds = None
    pred_source = None
    if garmin_pred:
        est_seconds = garmin_pred["predicted_time_s"]
        pred_source = "Garmin (VO2max)"
    elif riegel_pred:
        est_seconds = riegel_pred["predicted_time_s"]
        pred_source = "Riegel"
    elif distance_m > 0 and sport == "run":
        # Pace estimado 6:00/km como fallback
        est_seconds = distance_m / 1000 * 360
        pred_source = "estimativa generica"

    if not est_seconds:
        return None

    duration_h = est_seconds / 3600

    # Hidratacao
    fluid_ml_per_h = 600  # moderada
    fluid_total_ml = int(fluid_ml_per_h * duration_h)

    # Carbs
    if duration_h < 1:
        carbs_g_per_h = 0
        carbs_msg = "Não precisa repor — só água."
    elif duration_h < 2.5:
        carbs_g_per_h = 45
        carbs_msg = "Repor a partir de 45min — gel ou sport drink."
    else:
        carbs_g_per_h = 75
        carbs_msg = "Repor desde o início — múltiplas fontes (gel + drink + barra)."
    carbs_total_g = int(carbs_g_per_h * duration_h)

    # Sodio
    sodium_mg_per_h = 500 if duration_h > 1.5 else 300

    # Pace alvo em min/km (so pra running/swim)
    pace_alvo = None
    if sport == "run" and distance_m > 0:
        pace_alvo = est_seconds / (distance_m / 1000)

    # Splits (corrida): tempo a cada km/5km
    splits = []
    if sport == "run" and distance_m > 0 and pace_alvo:
        # Splits de 1km pra distancias <= 10km, senao splits de 5km
        split_dist = 1000 if distance_m <= 10000 else 5000
        n_splits = int(distance_m // split_dist)
        for i in range(1, n_splits + 1):
            split_time = pace_alvo * (i * split_dist / 1000)
            splits.append({
                "km": int(i * split_dist / 1000),
                "cumulative_s": int(split_time),
            })

    return {
        "estimated_duration_s": int(est_seconds),
        "estimated_duration_label": _format_duration(est_seconds),
        "prediction_source": pred_source,
        "pace_alvo_s_km": int(pace_alvo) if pace_alvo else None,
        "fluid_ml_per_h": fluid_ml_per_h,
        "fluid_total_ml": fluid_total_ml,
        "carbs_g_per_h": carbs_g_per_h,
        "carbs_total_g": carbs_total_g,
        "carbs_message": carbs_msg,
        "sodium_mg_per_h": sodium_mg_per_h,
        "splits": splits,
    }


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h{m:02d}min"
    return f"{m}min{s:02d}s"


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
    """Pega predicao do Garmin pra distancia da prova (corridas).

    Quando a distancia exata nao tem predicao Garmin (ex: prova de 6km mas
    Garmin so' calcula 5/10/half/marathon), escala via Riegel a partir da
    predicao mais proxima.
    """
    sport = race_row["sport"]
    if sport != "run":
        return None
    dist = race_row["distance_m"]
    if not dist:
        return None

    pred = garmin_metrics.garmin_race_predictions()
    if not pred or not pred.get("predictions"):
        return None
    closest = min(pred["predictions"], key=lambda p: abs(p["distance_m"] - dist))
    diff_pct = abs(closest["distance_m"] - dist) / dist * 100
    if diff_pct > 40:
        return None

    # Aplica Riegel pra escalar se distancia diferente (T2 = T1 * (D2/D1)^1.06)
    if abs(closest["distance_m"] - dist) > 50:
        scale = (dist / closest["distance_m"]) ** 1.06
        scaled_time_s = closest["predicted_time_s"] * scale
    else:
        scaled_time_s = closest["predicted_time_s"]
    scaled_pace_s_km = scaled_time_s / (dist / 1000)
    return {
        "predicted_time_s": int(scaled_time_s),
        "predicted_pace_s_km": int(scaled_pace_s_km),
        "based_on_label": closest["label"],
        "base_distance_m": closest["distance_m"],
        "approximation": diff_pct > 5,
        "scaled_via_riegel": abs(closest["distance_m"] - dist) > 50,
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
