"""Evolucao tecnica de natacao: serie temporal de DPS/SWOLF/cadencia/pace puro.

DPS (Distance Per Stroke) sai do raw via poolLength / avgStrokes — disponivel em
quase todo o historico. SWOLF e cadencia so' aparecem em atividades mais recentes
(provavelmente apos firmware do relogio). Pace puro depende de movingDuration.

Devolve sessoes + medias moveis (4 sessoes) + delta entre ultimas 4 e 4 anteriores.
Frontend usa pra plotar tendencia.
"""
from __future__ import annotations

import json
from typing import Any

from ..db import connect


# Alvos pra dashboard (banda intermediaria pra triatleta amadora, piscina 25m)
TARGETS = {
    "swolf": 38.0,
    "dps": 2.0,           # m/braçada
    "cadence": 30.0,       # strokes/min
    "pace_s_100m": 110.0,  # 1:50/100m
}


def _format_pace_per_100m(s_per_km: float) -> str:
    s_per_100 = s_per_km / 10.0
    m, s = divmod(int(round(s_per_100)), 60)
    return f"{m}:{s:02d}/100m"


def _pool_length_m(raw: dict) -> float | None:
    pl = raw.get("poolLength")
    if not pl:
        return None
    # GDPR vem em cm (factor=100), live API em m
    return pl / 100 if pl >= 50 else float(pl)


def _session_metrics(row: dict, raw: dict) -> dict[str, Any]:
    dps: float | None = None
    pool_m = _pool_length_m(raw)
    avg_strokes = raw.get("avgStrokes")
    if avg_strokes and pool_m:
        dps = round(pool_m / float(avg_strokes), 2)

    swolf = raw.get("averageSwolf")
    cad = raw.get("averageSwimCadenceInStrokesPerMinute")
    # GDPR export grava movingDuration em ms; live API em s. Normaliza por magnitude.
    moving_raw = raw.get("movingDuration")
    moving_s: float | None = None
    if moving_raw:
        moving_s = moving_raw / 1000 if moving_raw > 100_000 else float(moving_raw)
    pace_pure_s_100m: float | None = None
    if moving_s and row["distance_m"] and moving_s > 30:
        pace_pure_s_100m = round((moving_s / (row["distance_m"] / 1000)) / 10, 1)

    return {
        "activity_id": row["id"],
        "date": (row["started_at"] or "")[:10],
        "duration_min": round((row["duration_s"] or 0) / 60),
        "distance_m": int(row["distance_m"] or 0),
        "avg_hr": int(row["avg_hr"]) if row["avg_hr"] else None,
        "dps": dps,
        "swolf": float(swolf) if swolf else None,
        "cadence": float(cad) if cad else None,
        "pace_pure_s_100m": pace_pure_s_100m,
        "pace_pure_label": _format_pace_per_100m(pace_pure_s_100m * 10) if pace_pure_s_100m else None,
    }


def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def _delta(latest: list[float], previous: list[float]) -> float | None:
    a = _avg(latest)
    b = _avg(previous)
    if a is None or b is None:
        return None
    return round(a - b, 2)


def swim_technique_progress(limit: int = 12) -> dict[str, Any]:
    """Retorna ultimas `limit` natacoes ordenadas crescente (mais antiga primeiro)
    e o resumo da ultima + tendencia (delta da media das 4 ultimas vs 4 anteriores).
    """
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, started_at, duration_s, distance_m, avg_hr, raw
            FROM activities
            WHERE sport='swim'
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if not rows:
        return {"available": False, "sessions": [], "targets": TARGETS}

    sessions: list[dict[str, Any]] = []
    for r in rows:
        try:
            raw = json.loads(r["raw"] or "{}")
        except (json.JSONDecodeError, ValueError, TypeError):
            raw = {}
        sessions.append(_session_metrics(dict(r), raw))

    # Ordem crescente pra plotagem
    sessions.reverse()

    # Tendencias: media das ultimas 4 vs 4 anteriores (8 sessoes minimo).
    n = len(sessions)
    trends: dict[str, dict[str, Any]] = {}
    if n >= 4:
        last4 = sessions[-4:]
        prev4 = sessions[-8:-4] if n >= 8 else []
        for key in ("dps", "swolf", "cadence", "pace_pure_s_100m"):
            latest_vals = [s[key] for s in last4 if s[key] is not None]
            prev_vals = [s[key] for s in prev4 if s[key] is not None]
            current = _avg(latest_vals)
            delta = _delta(latest_vals, prev_vals) if prev_vals else None
            # Melhoria depende da metrica: dps/cadence subir eh bom, swolf/pace descer eh bom
            improvement: str | None = None
            if delta is not None:
                if key in ("dps", "cadence"):
                    improvement = "up" if delta > 0 else ("flat" if delta == 0 else "down")
                else:  # swolf, pace_pure
                    improvement = "up" if delta < 0 else ("flat" if delta == 0 else "down")
            trends[key] = {
                "current": current,
                "delta": delta,
                "improvement": improvement,
                "samples_current": len(latest_vals),
                "samples_previous": len(prev_vals),
            }

    latest = sessions[-1]
    insights: list[str] = []
    if trends:
        t_dps = trends.get("dps", {})
        if t_dps.get("delta") is not None and t_dps["delta"] >= 0.05:
            insights.append(
                f"DPS subiu {t_dps['delta']:+.2f}m/braçada vs últimas 4 sessões — "
                "deslize mais longo, sinal de técnica progredindo."
            )
        elif t_dps.get("delta") is not None and t_dps["delta"] <= -0.05:
            insights.append(
                f"DPS caiu {t_dps['delta']:+.2f}m/braçada — pode ser cansaço ou volume alto. "
                "Vale incluir sessão de drills (catch-up + fingertip drag)."
            )
        t_sw = trends.get("swolf", {})
        if t_sw.get("delta") is not None and t_sw["delta"] <= -1:
            insights.append(f"SWOLF reduziu {t_sw['delta']:+.0f} pontos — você está ficando mais eficiente.")
        elif t_sw.get("delta") is not None and t_sw["delta"] >= 1:
            insights.append(f"SWOLF subiu {t_sw['delta']:+.0f} pontos — perdendo eficiência, revisar técnica.")
        t_cad = trends.get("cadence", {})
        if t_cad.get("delta") is not None and t_cad["delta"] >= 1:
            insights.append(f"Cadência subiu {t_cad['delta']:+.0f} strokes/min — ritmo mais ativo, bom pra séries fortes.")
        if not insights:
            insights.append("Métricas estáveis nas últimas semanas — bom momento pra adicionar um foco específico (cadência ou drills).")

    return {
        "available": True,
        "count": n,
        "sessions": sessions,
        "latest": latest,
        "trends": trends,
        "targets": TARGETS,
        "insights": insights,
    }
