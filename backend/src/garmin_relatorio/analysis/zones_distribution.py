"""Distribuicao de tempo nas zonas Z1-Z5 por treino e por semana.

Le `hrTimeInZone_0..5` (segundos) do raw das atividades. Z0 = abaixo de Z1.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from ..db import connect


def _zones_for_activity(raw_str: str | None) -> dict[str, int] | None:
    if not raw_str:
        return None
    try:
        raw = json.loads(raw_str)
    except json.JSONDecodeError:
        return None
    zones = {}
    for i in range(6):
        k = f"hrTimeInZone_{i}"
        v = raw.get(k)
        if v is not None:
            # exporta GDPR vem em ms; live API tambem em ms
            zones[f"z{i}"] = int(v / 1000)
    return zones if zones else None


def weekly_zone_distribution(days: int = 84, sport: str | None = None) -> list[dict]:
    """Soma de segundos por zona, por semana. Opcionalmente filtrado por sport."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with connect() as conn:
        if sport:
            df = pd.read_sql_query(
                """
                SELECT id, sport, started_at, raw FROM activities
                WHERE started_at >= ? AND sport = ?
                """,
                conn,
                params=(cutoff, sport),
            )
        else:
            df = pd.read_sql_query(
                """
                SELECT id, sport, started_at, raw FROM activities
                WHERE started_at >= ?
                """,
                conn,
                params=(cutoff,),
            )
    if df.empty:
        return []

    df["started_at"] = pd.to_datetime(df["started_at"])
    df["week_start"] = df["started_at"].dt.to_period("W-MON").dt.start_time.dt.date

    rows: list[dict] = []
    for _, r in df.iterrows():
        zones = _zones_for_activity(r["raw"])
        if not zones:
            continue
        rows.append({"week_start": r["week_start"], **zones})

    if not rows:
        return []

    by_week = pd.DataFrame(rows).groupby("week_start").sum(numeric_only=True).reset_index()
    out = []
    for _, w in by_week.iterrows():
        # so retorna semanas que tem alguma zona
        zone_total = sum(w[c] for c in by_week.columns if c.startswith("z"))
        if zone_total == 0:
            continue
        out.append(
            {
                "week_start": w["week_start"].isoformat(),
                "z0_min": int(w.get("z0", 0) // 60),
                "z1_min": int(w.get("z1", 0) // 60),
                "z2_min": int(w.get("z2", 0) // 60),
                "z3_min": int(w.get("z3", 0) // 60),
                "z4_min": int(w.get("z4", 0) // 60),
                "z5_min": int(w.get("z5", 0) // 60),
                "total_min": int(zone_total // 60),
            }
        )
    return out


def polarization_index(days: int = 28, sport: str | None = None) -> dict:
    """Razao tempo Z1+Z2 / tempo Z3+ (proxy do '80/20 polarized').

    Saudavel: ~80% em Z1-Z2, ~20% em Z4-Z5, MINIMO em Z3.
    Opcionalmente filtrado por sport.
    """
    empty = {
        "days": days,
        "total_min": 0,
        "low_pct": None,
        "mid_pct": None,
        "high_pct": None,
        "verdict": "sem_dados",
        "message": "Sem dados de zonas para o período.",
    }
    weeks = weekly_zone_distribution(days, sport=sport)
    if not weeks:
        return empty
    total = sum(w["total_min"] for w in weeks)
    if total == 0:
        return empty
    low = sum(w["z1_min"] + w["z2_min"] for w in weeks)
    mid = sum(w["z3_min"] for w in weeks)
    high = sum(w["z4_min"] + w["z5_min"] for w in weeks)

    low_pct = round(100 * low / total, 1)
    mid_pct = round(100 * mid / total, 1)
    high_pct = round(100 * high / total, 1)

    if low_pct >= 75 and high_pct >= 10 and mid_pct < 20:
        verdict = "polarizado"
        msg = "Distribuição polarizada (80/20). Modelo classico de elite."
    elif mid_pct >= 35:
        verdict = "limiar"
        msg = "Muito tempo em Z3 (zona cinza). Risco de cansaco sem ganho proporcional."
    elif low_pct >= 80 and high_pct < 5:
        verdict = "base"
        msg = "Quase tudo em base aerobica. Bom pra construir volume; falta intensidade."
    else:
        verdict = "misto"
        msg = "Distribuicao mista. Sem padrao polarizado claro."

    return {
        "days": days,
        "total_min": total,
        "low_pct": low_pct,
        "mid_pct": mid_pct,
        "high_pct": high_pct,
        "verdict": verdict,
        "message": msg,
    }
