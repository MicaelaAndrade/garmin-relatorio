"""Evolucao tecnica de corrida — running dynamics do acelerometro (limpos).

As metricas de forma vem do IMU (acelerometro), nao do barometro, entao NAO
foram afetadas pelo glitch do altimetro (out/2025+). Confirmado: vertical ratio
e GCT estaveis pre/pos glitch. Potencia de corrida fica de FORA — ela deriva do
barometro e corrompeu junto (normPower/maxPower implausiveis no periodo recente).

Quatro metricas, espelhando swim_technique.py:
1. Vertical ratio (oscilacao/passada %) — economia de corrida. Menor = melhor. <8% bom.
2. Cadencia (passos/min, 2 pes) — coluna avg_cadence. Maior tende a reduzir lesao. ~170 alvo.
3. GCT (tempo de contato com solo, ms) — menor = mais reativa. ~250 alvo.
4. Comprimento de passada (cm) — contexto (depende do pace), sem alvo fixo.

Devolve sessoes (ordem crescente) + tendencia (media 4 ultimas vs 4 anteriores) + insights.
"""
from __future__ import annotations

import json
from typing import Any

from ..db import connect


TARGETS = {
    "vertical_ratio": 8.0,   # % — abaixo disso = corrida economica
    "cadence": 170.0,        # passos/min (2 pes)
    "gct": 250.0,            # ms — tempo de contato com solo
}


def _session_metrics(row: dict, raw: dict) -> dict[str, Any]:
    vr = raw.get("avgVerticalRatio")
    gct = raw.get("avgGroundContactTime")
    stride = raw.get("avgStrideLength")
    vosc = raw.get("avgVerticalOscillation")

    pace_s_km: float | None = None
    if row["distance_m"] and row["duration_s"] and row["distance_m"] > 500:
        pace_s_km = round(row["duration_s"] / (row["distance_m"] / 1000))

    return {
        "activity_id": row["id"],
        "date": (row["started_at"] or "")[:10],
        "duration_min": round((row["duration_s"] or 0) / 60),
        "distance_km": round((row["distance_m"] or 0) / 1000, 1),
        "avg_hr": int(row["avg_hr"]) if row["avg_hr"] else None,
        "pace_s_km": pace_s_km,
        "vertical_ratio": round(float(vr), 1) if vr else None,
        "vertical_oscillation": round(float(vosc), 1) if vosc else None,
        "cadence": round(float(row["avg_cadence"])) if row["avg_cadence"] else None,
        "gct": round(float(gct)) if gct else None,
        "stride_length": round(float(stride), 1) if stride else None,
    }


def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def _trend_for(sessions: list[dict], key: str, better: str) -> dict[str, Any]:
    with_val = [s for s in sessions if s.get(key) is not None]
    last4 = with_val[-4:]
    prev4 = with_val[-8:-4]
    current = _avg([s[key] for s in last4])
    delta = None
    improvement = None
    if last4 and prev4:
        prev_avg = _avg([s[key] for s in prev4])
        if current is not None and prev_avg is not None:
            delta = round(current - prev_avg, 2)
            if delta == 0:
                improvement = "flat"
            elif better == "up":
                improvement = "up" if delta > 0 else "down"
            else:
                improvement = "up" if delta < 0 else "down"
    return {
        "current": current,
        "delta": delta,
        "improvement": improvement,
        "samples_current": len(last4),
        "samples_previous": len(prev4),
    }


def run_technique_progress(limit: int = 16) -> dict[str, Any]:
    """Ultimas `limit` corridas (ordem crescente) + tendencias + insights."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, started_at, duration_s, distance_m, avg_hr, avg_cadence, raw
            FROM activities
            WHERE sport='run'
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
    sessions.reverse()

    n = len(sessions)
    trends = {
        "vertical_ratio": _trend_for(sessions, "vertical_ratio", better="down"),
        "cadence": _trend_for(sessions, "cadence", better="up"),
        "gct": _trend_for(sessions, "gct", better="down"),
        "stride_length": _trend_for(sessions, "stride_length", better="up"),
    }

    latest = next((s for s in reversed(sessions) if s["vertical_ratio"] is not None), sessions[-1])
    insights = _build_insights(trends, latest)

    return {
        "available": True,
        "count": n,
        "sessions": sessions,
        "latest": latest,
        "trends": trends,
        "targets": TARGETS,
        "insights": insights,
        "power_excluded": True,  # potencia corrompida pelo glitch do barômetro
    }


def _build_insights(trends: dict, latest: dict) -> list[str]:
    insights: list[str] = []

    t_cad = trends["cadence"]
    if t_cad["current"] is not None:
        if t_cad["current"] < 165:
            insights.append(
                f"Cadência média em ~{t_cad['current']:.0f} passos/min — abaixo da faixa "
                "alvo (170–180). Subir a cadência (passos mais curtos e rápidos) costuma "
                "reduzir impacto no joelho. Tente +5 spm gradualmente."
            )
        elif t_cad["delta"] is not None and t_cad["delta"] >= 2:
            insights.append(f"Cadência subiu {t_cad['delta']:+.0f} spm — ótimo, ritmo de passada mais ativo.")

    t_vr = trends["vertical_ratio"]
    if t_vr["current"] is not None:
        if t_vr["delta"] is not None and t_vr["delta"] <= -0.3:
            insights.append(
                f"Vertical ratio caiu {t_vr['delta']:+.1f}pp — você está oscilando menos pra "
                "frente/cima, corrida mais econômica. Sinal claro de progresso técnico."
            )
        elif t_vr["current"] > 9:
            insights.append(
                f"Vertical ratio em ~{t_vr['current']:.1f}% (alvo <8%) — há margem pra ganhar "
                "economia. Drills de cadência alta e fortalecimento de panturrilha ajudam."
            )

    t_gct = trends["gct"]
    if t_gct["current"] is not None and t_gct["delta"] is not None and t_gct["delta"] <= -5:
        insights.append(
            f"Tempo de contato com solo reduziu {t_gct['delta']:+.0f}ms — pisada mais reativa, "
            "menos tempo 'parada' no chão."
        )

    if not insights:
        insights.append("Forma de corrida estável nas últimas semanas. Pra evoluir, foque em cadência alta nos rodados leves.")

    return insights
