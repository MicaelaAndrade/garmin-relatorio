"""Ciclo menstrual × performance.

Cruza atividades com fase do ciclo (do `cycle.py`) e mostra média de pace,
FC e TRIMP por fase pra ver se há padrão.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from ..db import connect


PHASE_LABEL = {
    "menstrual": "Menstrual",
    "folicular": "Folicular",
    "ovulatoria": "Ovulatória",
    "lutea": "Lútea",
}

PHASE_COLOR = {
    "menstrual": "#ef4444",
    "folicular": "#4ade80",
    "ovulatoria": "#fbbf24",
    "lutea": "#60a5fa",
}


def _phase_for_day(day: date, cycles: list[dict]) -> str | None:
    """Determina fase do ciclo pra uma data específica."""
    # Encontra o ciclo cujo período inclua esse dia
    for c in cycles:
        start = c["start_date"]
        next_start = c.get("next_start") or (start + timedelta(days=c.get("predicted_cycle_length") or 28))
        if start <= day < next_start:
            day_in_cycle = (day - start).days + 1
            period_len = c.get("predicted_period_length") or 5
            cycle_len = c.get("predicted_cycle_length") or 28
            if day_in_cycle <= period_len:
                return "menstrual"
            ovulation_day = cycle_len - 14  # ovulação ~14d antes do próximo período
            if day_in_cycle < ovulation_day - 2:
                return "folicular"
            if abs(day_in_cycle - ovulation_day) <= 2:
                return "ovulatoria"
            return "lutea"
    return None


def cycle_performance(days: int = 180) -> dict[str, Any]:
    """Agrega métricas de treino por fase do ciclo nos últimos N dias."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        cycle_rows = conn.execute(
            "SELECT start_date, predicted_cycle_length, predicted_period_length FROM menstrual_cycles ORDER BY start_date"
        ).fetchall()
        if not cycle_rows:
            return {"available": False, "reason": "Sem dados de ciclo menstrual ingeridos."}

        cycles_data: list[dict] = []
        for i, r in enumerate(cycle_rows):
            cycles_data.append({
                "start_date": date.fromisoformat(r["start_date"]),
                "predicted_cycle_length": r["predicted_cycle_length"],
                "predicted_period_length": r["predicted_period_length"],
                "next_start": date.fromisoformat(cycle_rows[i + 1]["start_date"]) if i + 1 < len(cycle_rows) else None,
            })

        act_df = pd.read_sql_query(
            """
            SELECT sport, started_at, duration_s, distance_m, avg_hr, avg_pace_s_km, calories
            FROM activities
            WHERE started_at >= ? AND sport IN ('run', 'bike', 'swim')
              AND duration_s > 600
            """,
            conn,
            params=(cutoff,),
        )

    if act_df.empty:
        return {"available": False, "reason": "Sem atividades cardio no período."}

    act_df["started_at"] = pd.to_datetime(act_df["started_at"])
    act_df["day"] = act_df["started_at"].dt.date
    act_df["phase"] = act_df["day"].apply(lambda d: _phase_for_day(d, cycles_data))
    classified = act_df[act_df["phase"].notna()]
    if classified.empty:
        return {"available": False, "reason": "Não foi possível mapear atividades ao ciclo."}

    by_phase = []
    for phase in ("menstrual", "folicular", "ovulatoria", "lutea"):
        sub = classified[classified["phase"] == phase]
        if sub.empty:
            continue
        avg_pace = sub["avg_pace_s_km"].dropna().mean()
        avg_hr = sub["avg_hr"].dropna().mean()
        avg_dur = sub["duration_s"].mean() / 60
        total_km = sub["distance_m"].fillna(0).sum() / 1000
        by_phase.append({
            "phase": phase,
            "label": PHASE_LABEL[phase],
            "color": PHASE_COLOR[phase],
            "sessions": int(len(sub)),
            "avg_duration_min": round(float(avg_dur), 1),
            "total_km": round(float(total_km), 1),
            "avg_pace_s_km": int(avg_pace) if pd.notna(avg_pace) else None,
            "avg_hr": int(avg_hr) if pd.notna(avg_hr) else None,
        })

    # Comparações: qual fase tem melhor pace? maior duração?
    insights: list[str] = []
    with_pace = [p for p in by_phase if p["avg_pace_s_km"]]
    if len(with_pace) >= 2:
        best_pace = min(with_pace, key=lambda p: p["avg_pace_s_km"])
        worst_pace = max(with_pace, key=lambda p: p["avg_pace_s_km"])
        diff = worst_pace["avg_pace_s_km"] - best_pace["avg_pace_s_km"]
        if diff > 10:
            insights.append(
                f"Pace mais rápido na fase {best_pace['label']} ({_fmt_pace(best_pace['avg_pace_s_km'])}/km), "
                f"mais lento em {worst_pace['label']} ({_fmt_pace(worst_pace['avg_pace_s_km'])}/km) — diferença {diff}s/km."
            )

    by_volume = sorted(by_phase, key=lambda p: p["sessions"], reverse=True)
    if by_volume:
        insights.append(f"Mais treinos: {by_volume[0]['label']} ({by_volume[0]['sessions']} sessões).")

    return {
        "available": True,
        "days": days,
        "total_sessions_classified": int(len(classified)),
        "by_phase": by_phase,
        "insights": insights,
    }


def _fmt_pace(s_km: int) -> str:
    m, s = divmod(int(s_km), 60)
    return f"{m}:{s:02d}"
