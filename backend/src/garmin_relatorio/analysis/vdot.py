"""VDOT (Jack Daniels) — VO2max equivalente baseado em performance recente.

Pega o melhor pace em distância >= 3km dos últimos 60 dias e calcula um VDOT
aproximado pela fórmula de Daniels. A partir do VDOT, sugere paces:
- Easy (E): 60-79% VDOT — base aeróbica
- Marathon (M): 75-84%
- Threshold (T): 88-92% — limiar
- Interval (I): 95-100% — VO2max
- Repetition (R): 105%+ — neuromuscular

Referência: Daniels' Running Formula (Jack Daniels, 2014).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..db import connect


def _vdot_from_race(distance_m: float, duration_s: float) -> float:
    """Aproximação Daniels: vDOT depende da velocidade de prova e duração.

    Formula:
        velocity_m_min = distance / (duration/60)
        Percent of VO2max sustainable at duration:
            pct = 0.8 + 0.1894393 × exp(-0.012778 × t_min)
                + 0.2989558 × exp(-0.1932605 × t_min)
        VO2_running = -4.60 + 0.182258 × v + 0.000104 × v²
        VDOT = VO2_running / pct
    """
    import math

    t_min = duration_s / 60
    v = distance_m / t_min  # m/min
    vo2 = -4.60 + 0.182258 * v + 0.000104 * v ** 2
    pct = (
        0.8
        + 0.1894393 * math.exp(-0.012778 * t_min)
        + 0.2989558 * math.exp(-0.1932605 * t_min)
    )
    return vo2 / pct


def _pace_for_velocity(velocity_m_min: float) -> int:
    """m/min -> segundos/km. Inverte: 1km = 1000m, então pace_min/km = 1000/v."""
    if velocity_m_min <= 0:
        return 0
    pace_min_per_km = 1000 / velocity_m_min
    return int(pace_min_per_km * 60)


def _velocity_from_vdot_pct(vdot: float, pct: float) -> float:
    """Daniels: dado o VDOT e a % alvo, resolve a velocidade.

    VO2 = -4.60 + 0.182258 * v + 0.000104 * v²
    pct = VO2 / VDOT
    pct × VDOT = -4.60 + 0.182258 * v + 0.000104 * v²
    Quadratica: 0.000104 v² + 0.182258 v - (4.60 + pct × VDOT) = 0
    """
    a = 0.000104
    b = 0.182258
    c = -(4.60 + pct * vdot)
    disc = b * b - 4 * a * c
    if disc < 0:
        return 0
    return (-b + disc ** 0.5) / (2 * a)


def vdot_dashboard() -> dict[str, Any]:
    """Calcula VDOT da melhor performance recente em corrida + paces de treino."""
    cutoff = (date.today() - timedelta(days=60)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, started_at, distance_m, duration_s, avg_pace_s_km
            FROM activities
            WHERE sport = 'run' AND started_at >= ?
              AND distance_m >= 3000 AND duration_s > 300
            ORDER BY started_at DESC
            """,
            (cutoff,),
        ).fetchall()

    if not rows:
        return {"available": False, "reason": "Nenhuma corrida >= 3km nos últimos 60 dias."}

    # Pega a melhor performance (maior VDOT)
    best_vdot = 0.0
    best_row = None
    for r in rows:
        try:
            v = _vdot_from_race(float(r["distance_m"]), float(r["duration_s"]))
            if v > best_vdot:
                best_vdot = v
                best_row = r
        except Exception:
            continue

    if best_vdot == 0 or best_row is None:
        return {"available": False, "reason": "Não foi possível calcular VDOT."}

    # Paces sugeridos (% VDOT)
    targets = {
        "easy": (0.65, "Easy/Long", "Base aeróbica — conversa fluida, FC < 75% max"),
        "marathon": (0.84, "Maratona", "Pace de maratona — controlado e sustentável"),
        "threshold": (0.90, "Tempo/Threshold", "Limiar — desconfortável mas controlado por 20-40min"),
        "interval": (0.98, "Intervalos (VO2max)", "Esforço máximo sustentável por 3-5min"),
        "repetition": (1.10, "Repetições (R)", "Neuromuscular — 200-400m forte"),
    }
    paces = []
    for key, (pct, label, descr) in targets.items():
        v = _velocity_from_vdot_pct(best_vdot, pct)
        pace_s_km = _pace_for_velocity(v)
        paces.append({
            "key": key,
            "label": label,
            "pct_vdot": int(pct * 100),
            "pace_s_km": pace_s_km,
            "description": descr,
        })

    return {
        "available": True,
        "vdot": round(best_vdot, 1),
        "based_on": {
            "activity_id": best_row["id"],
            "started_at": best_row["started_at"],
            "distance_km": round(best_row["distance_m"] / 1000, 2),
            "duration_s": int(best_row["duration_s"]),
            "pace_s_km": int(best_row["avg_pace_s_km"]) if best_row["avg_pace_s_km"] else None,
        },
        "paces": paces,
    }
