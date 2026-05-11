"""Cycle phase tracker — fase atual, historico, previsao + sugestao de treino.

Fases (modelo simplificado, 28-32 dias):
- menstrual (dias 1-5): performance pode cair, priorize recuperacao
- folicular (dias 6 ao dia da ovulacao, ~6-13): janela de melhor performance
- ovulatoria (dia ~14): pico de performance, leve aumento risco lesao
- lutea (dias 15-28): mais fadiga, melhor pra aerobico estavel

Referencias:
- Sims SM, Heather AK. Myths and Methodologies: Reducing Scientific Design
  Ambiguity in Studies Comparing Sexes and/or Menstrual Cycle Phases.
  Exp Physiol 2018.
- Mclnnis MN et al. The Influence of the Menstrual Cycle on Performance.
  Sports Medicine 2017.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from statistics import mean

from ..db import connect


def _all_cycles() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT start_date, predicted_cycle_length, actual_cycle_length,
                   predicted_period_length, actual_period_length,
                   fertile_window_start, fertile_window_length, status, cycle_type
            FROM menstrual_cycles ORDER BY start_date DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def _phase_for_day(cycle_day: int, period_length: int = 5) -> str:
    if cycle_day <= period_length:
        return "menstrual"
    if cycle_day <= 13:
        return "folicular"
    if cycle_day <= 15:
        return "ovulatoria"
    return "lutea"


def _phase_advice(phase: str) -> dict[str, str]:
    return {
        "menstrual": {
            "training": "Treino leve a moderado. Se o fluxo for forte, priorize "
            "recuperacao e mobilidade. Hidratacao e ferro merecem atencao.",
            "intensity": "Z1-Z2 predominante. Evite picos maximos se sentir queda.",
        },
        "folicular": {
            "training": "Janela de OURO pra performance e adaptacao. Bom momento "
            "pra treinos longos, intervalos e PRs.",
            "intensity": "Tudo OK — Z1 a Z5. Voce tolera melhor cargas altas.",
        },
        "ovulatoria": {
            "training": "Pico de performance, mas ligeiro aumento de risco de lesao "
            "ligamentar (estrogenio + relaxina). Aquecer bem.",
            "intensity": "Z1-Z5 OK. Cuidado com mudanças bruscas de direcao.",
        },
        "lutea": {
            "training": "Temperatura corporal mais alta, mais fadiga percebida. Bom pra "
            "aerobico estavel (Z2-Z3). Mais carbo nos dias mais quentes.",
            "intensity": "Z2-Z3 idealmente. Pode cair Z4-Z5 se sentir bem.",
        },
    }.get(phase, {"training": "", "intensity": ""})


def current_phase() -> dict:
    cycles = _all_cycles()
    if not cycles:
        return {"available": False, "reason": "Sem dados de ciclo no banco."}

    today = date.today()
    # Pega o ciclo mais recente cujo start <= hoje
    current = None
    for c in cycles:
        start = datetime.fromisoformat(c["start_date"]).date()
        if start <= today:
            current = c
            break

    if not current:
        return {"available": False, "reason": "Nenhum ciclo iniciado ainda."}

    start_date = datetime.fromisoformat(current["start_date"]).date()
    days_since = (today - start_date).days
    cycle_day = days_since + 1  # 1-indexed

    # Estima cycle length: usa media dos ciclos passados (actualCycleLength)
    past_lengths = [
        c["actual_cycle_length"]
        for c in cycles
        if c["actual_cycle_length"] and c["start_date"] != current["start_date"]
    ]
    avg_cycle_length = round(mean(past_lengths)) if past_lengths else (
        current.get("predicted_cycle_length") or 28
    )

    period_length = current.get("actual_period_length") or current.get(
        "predicted_period_length") or 5

    # Se ja passou do cycle_length previsto, provavelmente novo ciclo nao foi logado
    if cycle_day > avg_cycle_length:
        # Estima novo ciclo "fantasma": dia = (cycle_day - 1) % avg_cycle_length + 1
        estimated_day = ((cycle_day - 1) % avg_cycle_length) + 1
        ciclo_estimado = True
        cycle_day = estimated_day
        days_since = cycle_day - 1
    else:
        ciclo_estimado = False

    phase = _phase_for_day(cycle_day, period_length)
    advice = _phase_advice(phase)

    next_period = today + timedelta(days=(avg_cycle_length - cycle_day + 1))

    return {
        "available": True,
        "cycle_day": cycle_day,
        "days_since_period_start": days_since,
        "phase": phase,
        "phase_label": {
            "menstrual": "Menstrual",
            "folicular": "Folicular",
            "ovulatoria": "Ovulatoria",
            "lutea": "Lutea",
        }[phase],
        "avg_cycle_length": avg_cycle_length,
        "period_length": period_length,
        "next_period_estimated": next_period.isoformat(),
        "training_advice": advice["training"],
        "intensity_advice": advice["intensity"],
        "estimated_cycle": ciclo_estimado,
    }


def cycle_history(limit: int = 12) -> dict:
    """Estatisticas de regularidade."""
    cycles = _all_cycles()[:limit]
    actual_lengths = [c["actual_cycle_length"] for c in cycles if c["actual_cycle_length"]]
    if not actual_lengths:
        return {"available": False, "cycles": cycles}

    avg = round(mean(actual_lengths), 1)
    minimum = min(actual_lengths)
    maximum = max(actual_lengths)
    variation = maximum - minimum
    regularity = "regular" if variation <= 4 else "irregular" if variation > 8 else "moderada"

    return {
        "available": True,
        "count": len(actual_lengths),
        "avg_length": avg,
        "min_length": minimum,
        "max_length": maximum,
        "variation_days": variation,
        "regularity": regularity,
        "recent_cycles": cycles[:6],
    }


def recent_logs(limit: int = 30) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT date, flow, symptoms, moods, ovulation_day FROM menstrual_logs ORDER BY date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["symptoms"] = json.loads(d["symptoms"] or "[]")
        d["moods"] = json.loads(d["moods"] or "[]")
        out.append(d)
    return out


def cycle_dashboard() -> dict:
    return {
        "current": current_phase(),
        "history": cycle_history(12),
        "recent_logs": recent_logs(30),
    }
