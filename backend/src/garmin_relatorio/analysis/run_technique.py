"""Evolucao tecnica de corrida — running dynamics do acelerometro (limpos).

As metricas de forma vem do IMU (acelerometro), nao do barometro, entao NAO
foram afetadas pelo glitch do altimetro (out/2025+). Confirmado: vertical ratio
e GCT estaveis pre/pos glitch.

Potencia de corrida: corrompeu junto com o barometro no FR165, entao SO entra
para atividades do FR265 (deviceId FR265_DEVICE_ID, trocado em 18/06/2026, com
barometro integro). Atividades anteriores ficam com power None — nao se confia
no normPower/maxPower do periodo do glitch.

Metricas de forma (espelhando swim_technique.py):
1. Vertical ratio (oscilacao/passada %) — economia de corrida. Menor = melhor. <8% bom.
2. Cadencia (passos/min, 2 pes) — coluna avg_cadence. Maior tende a reduzir lesao. ~170 alvo.
3. GCT (tempo de contato com solo, ms) — menor = mais reativa. ~250 alvo.
4. Comprimento de passada (cm) — contexto (depende do pace), sem alvo fixo.
5. Potencia normalizada (W, so FR265) — proxy de esforco sustentavel. + VI (constancia) + W/kg.

Devolve sessoes (ordem crescente) + tendencia (media 4 ultimas vs 4 anteriores) + insights.
"""
from __future__ import annotations

import json
from typing import Any

from ..db import connect


# Relogio com barometro integro (trocado 18/06/2026). So a potencia dele e confiavel.
FR265_DEVICE_ID = 3528945915

TARGETS = {
    "vertical_ratio": 8.0,   # % — abaixo disso = corrida economica
    "cadence": 170.0,        # passos/min (2 pes)
    "gct": 250.0,            # ms — tempo de contato com solo
    "variability_index": 1.05,  # norm/avg — abaixo disso = pacing constante
}


def _latest_weight_kg() -> float | None:
    """Peso mais recente (biometrics.weight_g) para calcular W/kg."""
    with connect() as conn:
        row = conn.execute(
            "SELECT weight_g FROM biometrics WHERE weight_g IS NOT NULL "
            "ORDER BY date DESC LIMIT 1"
        ).fetchone()
    if not row or not row["weight_g"]:
        return None
    return round(float(row["weight_g"]) / 1000, 1)


def _session_metrics(row: dict, raw: dict, weight_kg: float | None = None) -> dict[str, Any]:
    vr = raw.get("avgVerticalRatio")
    gct = raw.get("avgGroundContactTime")
    stride = raw.get("avgStrideLength")
    vosc = raw.get("avgVerticalOscillation")

    pace_s_km: float | None = None
    if row["distance_m"] and row["duration_s"] and row["distance_m"] > 500:
        pace_s_km = round(row["duration_s"] / (row["distance_m"] / 1000))

    # Potencia: SO do FR265 (barometro integro). FR165 corrompeu, fica None.
    avg_power = norm_power = max_power = variability_index = w_per_kg = None
    if raw.get("deviceId") == FR265_DEVICE_ID:
        ap = raw.get("avgPower")
        np_ = raw.get("normPower")
        mp = raw.get("maxPower")
        if ap:
            avg_power = round(float(ap))
        if np_:
            norm_power = round(float(np_))
        if mp:
            max_power = round(float(mp))
        if avg_power and norm_power:
            variability_index = round(norm_power / avg_power, 3)
        if norm_power and weight_kg:
            w_per_kg = round(norm_power / weight_kg, 2)

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
        "avg_power": avg_power,
        "norm_power": norm_power,
        "max_power": max_power,
        "variability_index": variability_index,
        "w_per_kg": w_per_kg,
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

    weight_kg = _latest_weight_kg()

    sessions: list[dict[str, Any]] = []
    for r in rows:
        try:
            raw = json.loads(r["raw"] or "{}")
        except (json.JSONDecodeError, ValueError, TypeError):
            raw = {}
        sessions.append(_session_metrics(dict(r), raw, weight_kg))
    sessions.reverse()

    n = len(sessions)
    power_available = any(s["norm_power"] is not None for s in sessions)
    trends = {
        "vertical_ratio": _trend_for(sessions, "vertical_ratio", better="down"),
        "cadence": _trend_for(sessions, "cadence", better="up"),
        "gct": _trend_for(sessions, "gct", better="down"),
        "stride_length": _trend_for(sessions, "stride_length", better="up"),
    }
    if power_available:
        trends["norm_power"] = _trend_for(sessions, "norm_power", better="up")
        trends["variability_index"] = _trend_for(sessions, "variability_index", better="down")

    latest = next((s for s in reversed(sessions) if s["vertical_ratio"] is not None), sessions[-1])
    latest_power = next((s for s in reversed(sessions) if s["norm_power"] is not None), None)
    insights = _build_insights(trends, latest, latest_power)

    return {
        "available": True,
        "count": n,
        "sessions": sessions,
        "latest": latest,
        "trends": trends,
        "targets": TARGETS,
        "insights": insights,
        "power_available": power_available,
        "weight_kg": weight_kg,
        # potencia agora entra para o FR265 (barometro integro); FR165 segue excluido
        "power_excluded": False,
    }


def _build_insights(trends: dict, latest: dict, latest_power: dict | None = None) -> list[str]:
    insights: list[str] = []

    if latest_power and latest_power.get("variability_index") is not None:
        vi = latest_power["variability_index"]
        np_ = latest_power.get("norm_power")
        wkg = latest_power.get("w_per_kg")
        extra = f" (~{np_}W" + (f", {wkg} W/kg" if wkg else "") + ")" if np_ else ""
        if vi <= TARGETS["variability_index"]:
            insights.append(
                f"Pacing de potência constante — índice de variabilidade {vi:.3f} "
                f"(alvo ≤{TARGETS['variability_index']}){extra}. Esforço bem distribuído."
            )
        else:
            insights.append(
                f"Índice de variabilidade de potência em {vi:.3f} (alvo ≤{TARGETS['variability_index']})"
                f"{extra} — esforço oscilou. Em rodados leves, segure a potência mais estável."
            )

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
