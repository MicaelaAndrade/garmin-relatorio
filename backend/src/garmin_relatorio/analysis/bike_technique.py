"""Evolucao tecnica de ciclismo — sem power meter, foco no que os dados permitem.

Sem medidor de potencia (zero atividades com watts) e cadencia confiavel so' em
12/110 pedaladas. Em vez de proxies fracos, este modulo entrega tres analises
honestas pros dados disponiveis:

1. Indice de eficiencia aerobica = velocidade media (km/h) / FC media * 100.
   Sobe ao longo do tempo = ficando mais forte na bike (melhor proxy sem potencia).
   Coberto em ~101/110 atividades (precisa GPS + FC).

2. Deriva cardiaca (cardiac decoupling) — usa splits pra comparar a eficiencia
   (velocidade/FC) da 1a metade vs 2a metade do treino. <5% = boa durabilidade
   aerobica. So' calcula em sessoes com >=4 splits e duracao razoavel (~51/110,
   concentrado no historico mais antigo — auto-lap foi desligado a pedido do treinador
   ~abr/2026, entao splits so' aparecem em treinos estruturados ou com volta manual).

3. RPE x FC — esforco percebido (workoutRpe 1-10) vs FC real. Calibra a percepcao.
   Existe em ~99/110, tambem concentrado no historico antigo.

Devolve sessoes (ordem crescente) + tendencia (media das 4 ultimas com dado vs 4
anteriores) + insights. Espelha o padrao de swim_technique.py.
"""
from __future__ import annotations

import json
from typing import Any

from ..db import connect


# Alvos pra dashboard (triatleta amadora, sem power meter)
TARGETS = {
    "efficiency": 17.0,   # km/h por 100 bpm — banda "boa" pra amadora
    "drift_pct": 5.0,     # deriva cardiaca <=5% = boa durabilidade aerobica
}

# Garmin grava workoutFeel em passos de 25 (0=pessimo .. 100=otimo)
_FEEL_LABELS = {0: "Péssimo", 25: "Ruim", 50: "Normal", 75: "Bom", 100: "Ótimo"}


def _feel_label(feel: float | None) -> str | None:
    if feel is None:
        return None
    nearest = min(_FEEL_LABELS, key=lambda k: abs(k - feel))
    return _FEEL_LABELS[nearest]


def _speed_kmh(row: dict, raw: dict) -> float | None:
    """km/h: usa coluna avg_speed_kmh; fallback distancia/duracao."""
    s = row.get("avg_speed_kmh")
    if s and s > 0:
        return float(s)
    dist = row.get("distance_m")
    dur = row.get("duration_s")
    if dist and dur and dur > 0:
        return round((dist / 1000) / (dur / 3600), 2)
    return None


def _split_measure(split: dict) -> dict[str, float]:
    """Achata a lista measurements de um split em {fieldEnum: value}."""
    out: dict[str, float] = {}
    for m in split.get("measurements", []) or []:
        if m.get("valid") and m.get("fieldEnum") and m.get("value") is not None:
            out[m["fieldEnum"]] = float(m["value"])
    return out


def _cardiac_drift_pct(raw: dict) -> float | None:
    """Deriva cardiaca: queda da eficiencia (vel/FC) da 1a pra 2a metade do treino.

    Positivo = FC subiu em relacao a velocidade (descolamento aerobico, ruim).
    Unidades de velocidade/FC se cancelam no ratio, entao usa valores brutos.
    Pondera cada split pela duracao. So' calcula com >=4 splits validos.
    """
    splits = raw.get("splits") or []
    parsed: list[tuple[float, float, float]] = []  # (hr, speed, dur)
    for sp in splits:
        mm = _split_measure(sp)
        hr = mm.get("WEIGHTED_MEAN_HEARTRATE")
        speed = mm.get("WEIGHTED_MEAN_MOVINGSPEED") or mm.get("WEIGHTED_MEAN_SPEED")
        dur = mm.get("SUM_MOVINGDURATION") or mm.get("SUM_DURATION")
        if hr and speed and dur and hr > 0 and speed > 0 and dur > 0:
            parsed.append((hr, speed, dur))
    if len(parsed) < 4:
        return None

    total = sum(d for _, _, d in parsed)
    if total <= 0:
        return None

    half = total / 2
    cum = 0.0
    first: list[tuple[float, float, float]] = []
    second: list[tuple[float, float, float]] = []
    for hr, speed, dur in parsed:
        (first if cum < half else second).append((hr, speed, dur))
        cum += dur
    if not first or not second:
        return None

    def weighted_eff(part: list[tuple[float, float, float]]) -> float:
        wd = sum(d for _, _, d in part)
        return sum((speed / hr) * d for hr, speed, d in part) / wd

    eff_first = weighted_eff(first)
    eff_second = weighted_eff(second)
    if eff_first <= 0:
        return None
    return round((eff_first - eff_second) / eff_first * 100, 1)


def _session_metrics(row: dict, raw: dict) -> dict[str, Any]:
    speed = _speed_kmh(row, raw)
    hr = row.get("avg_hr")
    efficiency = round(speed / hr * 100, 2) if speed and hr else None

    rpe_raw = raw.get("workoutRpe")
    rpe = round(rpe_raw / 10, 1) if rpe_raw else None  # Garmin grava 10-100 → 1-10
    feel = raw.get("workoutFeel")

    return {
        "activity_id": row["id"],
        "date": (row["started_at"] or "")[:10],
        "name": raw.get("name") or raw.get("activityName"),
        "duration_min": round((row["duration_s"] or 0) / 60),
        "distance_km": round((row["distance_m"] or 0) / 1000, 1),
        "avg_hr": int(hr) if hr else None,
        "avg_speed_kmh": round(speed, 1) if speed else None,
        "efficiency": efficiency,
        "cardiac_drift_pct": _cardiac_drift_pct(raw),
        "rpe": rpe,
        "feel": float(feel) if feel is not None else None,
        "feel_label": _feel_label(feel),
    }


def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def _trend_for(sessions: list[dict], key: str, better: str) -> dict[str, Any]:
    """Media das ultimas 4 sessoes COM dado vs as 4 anteriores com dado.

    Robusto a lacunas (drift/RPE sao esparsos). `better` = 'up' ou 'down'.
    """
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


def bike_technique_progress(limit: int = 24) -> dict[str, Any]:
    """Ultimas `limit` pedaladas (ordem crescente) + tendencias + insights.

    Janela mais larga que a natacao (24) porque drift/RPE concentram no historico
    mais antigo — precisamos alcançar essas sessoes pra ter tendencia.
    """
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, started_at, duration_s, distance_m, avg_hr, avg_speed_kmh, raw
            FROM activities
            WHERE sport='bike'
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
    sessions.reverse()  # crescente pra plotagem

    n = len(sessions)
    trends = {
        "efficiency": _trend_for(sessions, "efficiency", better="up"),
        "cardiac_drift_pct": _trend_for(sessions, "cardiac_drift_pct", better="down"),
        "rpe": _trend_for(sessions, "rpe", better="down"),
    }

    # Cobertura por metrica (pra avisar no card quando RPE/drift secaram)
    coverage = {
        "efficiency": sum(1 for s in sessions if s["efficiency"] is not None),
        "cardiac_drift_pct": sum(1 for s in sessions if s["cardiac_drift_pct"] is not None),
        "rpe": sum(1 for s in sessions if s["rpe"] is not None),
    }

    insights = _build_insights(sessions, trends, coverage, n)

    # latest = ultima sessao com eficiencia (a metrica densa)
    latest = next((s for s in reversed(sessions) if s["efficiency"] is not None), sessions[-1])

    return {
        "available": True,
        "count": n,
        "sessions": sessions,
        "latest": latest,
        "trends": trends,
        "coverage": coverage,
        "targets": TARGETS,
        "insights": insights,
        "no_power_meter": True,
    }


def _build_insights(
    sessions: list[dict], trends: dict, coverage: dict, n: int
) -> list[str]:
    insights: list[str] = []

    # 1. Eficiencia aerobica (carro-chefe)
    te = trends["efficiency"]
    if te["delta"] is not None and te["delta"] >= 0.4:
        insights.append(
            f"Eficiência aeróbica subiu {te['delta']:+.1f} (vel÷FC) vs as 4 pedaladas "
            "anteriores — você está sustentando mais velocidade com a mesma FC. "
            "É o sinal mais confiável de progresso na bike sem medidor de potência."
        )
    elif te["delta"] is not None and te["delta"] <= -0.4:
        insights.append(
            f"Eficiência aeróbica caiu {te['delta']:+.1f} — pode ser fadiga acumulada, "
            "calor, ou rotas mais difíceis. Vale uma semana mais leve pra checar."
        )
    elif te["current"] is not None:
        insights.append(
            f"Eficiência aeróbica estável (~{te['current']:.1f} km/h por 100 bpm). "
            "Pra subir, inclua um rodízio longo em Z2 firme por semana."
        )

    # 2. Deriva cardiaca
    td = trends["cardiac_drift_pct"]
    if coverage["cardiac_drift_pct"] == 0:
        insights.append(
            "Deriva cardíaca indisponível: as pedaladas recentes não têm splits "
            "(auto-lap desligado a pedido do treinador). Sem problema — treinos "
            "estruturados do coach e voltas marcadas na mão (botão lap) ainda geram "
            "splits, então a análise volta nesses dias sem mexer na config."
        )
    elif td["current"] is not None:
        if td["current"] <= 5:
            insights.append(
                f"Deriva cardíaca em ~{td['current']:.1f}% nas sessões com splits — "
                "abaixo de 5% indica boa durabilidade aeróbica (FC estável no esforço longo)."
            )
        else:
            insights.append(
                f"Deriva cardíaca em ~{td['current']:.1f}% — acima de 5% sugere que a FC "
                "sobe ao longo do treino. Base aeróbica ainda em construção; priorize Z2."
            )

    # 3. RPE x FC
    rpe_sessions = [s for s in sessions if s["rpe"] is not None and s["avg_hr"]]
    if coverage["rpe"] == 0:
        insights.append(
            "RPE×FC indisponível: as pedaladas recentes não registraram esforço percebido. "
            "Preencha o RPE no fim do treino no relógio pra calibrar percepção vs FC real."
        )
    elif rpe_sessions:
        hard = [s for s in rpe_sessions if s["rpe"] >= 7]
        easy = [s for s in rpe_sessions if s["rpe"] <= 3]
        if hard:
            hr_hard = _avg([s["avg_hr"] for s in hard])
            insights.append(
                f"Nos treinos que você sentiu fortes (RPE≥7), a FC média foi ~{hr_hard:.0f} bpm — "
                "confira se bate com sua Z4 real; se a FC estiver baixa, dá pra apertar mais."
            )
        elif easy:
            hr_easy = _avg([s["avg_hr"] for s in easy])
            insights.append(
                f"Nos treinos leves (RPE≤3), a FC média foi ~{hr_easy:.0f} bpm — "
                "bom pra confirmar que os dias fáceis estão realmente fáceis (Z1-Z2)."
            )

    return insights
