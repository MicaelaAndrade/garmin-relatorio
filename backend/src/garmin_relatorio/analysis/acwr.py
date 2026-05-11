"""Acute:Chronic Workload Ratio (ACWR) — risco de lesao.

Referencias:
- Gabbett TJ. The training-injury prevention paradox. Br J Sports Med 2016
- Hulin BT et al. Spikes in acute workload are associated with increased injury risk.
  BJSM 2014

Carga = duracao (min) * sRPE estimado pelo HR avg (TRIMP simplificado).
Quando HR ausente, usa apenas duracao (subestima).

Zona "sweet spot": ACWR 0.8 - 1.3
Risco moderado: 1.3 - 1.5
Risco alto: > 1.5 (carga aguda 50%+ acima da cronica)
Destreino: < 0.8 (perde adaptacao)
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from .hr_zones import trimp_for_activity
from .volume import load_activities_df


def _trimp(row) -> float:
    """TRIMP usando zonas FC reais do usuario (de hr_zones table)."""
    if pd.isna(row.avg_hr) or row.avg_hr is None:
        return trimp_for_activity(row.duration_min, None)
    return trimp_for_activity(row.duration_min, float(row.avg_hr))


def acwr_series(days: int = 90) -> list[dict]:
    """Serie diaria de ACWR (rolling 7d / rolling 28d)."""
    df = load_activities_df(days + 35)  # buffer para janela 28d
    if df.empty:
        return []

    df["load"] = df.apply(_trimp, axis=1)
    df["day"] = df["started_at"].dt.date

    # Carga diaria total
    daily = df.groupby("day", as_index=False)["load"].sum()
    # Reindex para incluir dias sem treino (load = 0)
    full_range = pd.date_range(daily["day"].min(), date.today(), freq="D").date
    daily = daily.set_index("day").reindex(full_range, fill_value=0).reset_index()
    daily.columns = ["day", "load"]

    daily["acute_7d"] = daily["load"].rolling(7, min_periods=1).mean()
    daily["chronic_28d"] = daily["load"].rolling(28, min_periods=7).mean()
    daily["acwr"] = daily["acute_7d"] / daily["chronic_28d"].replace(0, np.nan)
    daily["zone"] = daily["acwr"].apply(_zone)

    cutoff = date.today() - timedelta(days=days)
    daily = daily[daily["day"] >= cutoff]

    return [
        {
            "day": row.day.isoformat(),
            "load": round(float(row.load), 1),
            "acute_7d": round(float(row.acute_7d), 1) if pd.notna(row.acute_7d) else None,
            "chronic_28d": round(float(row.chronic_28d), 1)
            if pd.notna(row.chronic_28d)
            else None,
            "acwr": round(float(row.acwr), 2) if pd.notna(row.acwr) else None,
            "zone": row.zone,
        }
        for row in daily.itertuples()
    ]


def _zone(acwr: float | None) -> str:
    if acwr is None or pd.isna(acwr):
        return "indefinido"
    if acwr < 0.8:
        return "destreino"
    if acwr <= 1.3:
        return "otimo"
    if acwr <= 1.5:
        return "moderado"
    return "alto"


def current_status() -> dict:
    """Snapshot do dia: ACWR, zona, recomendacao."""
    series = acwr_series(days=14)
    if not series:
        return {"acwr": None, "zone": "sem_dados", "recommendation": "Sem treinos suficientes."}
    last = series[-1]
    rec = {
        "destreino": "Carga baixa. Tudo bem se for descanso planejado; senao retome gradual.",
        "otimo": "Zona ideal. Pode manter ou progredir 5-10% na proxima semana.",
        "moderado": "Cuidado com aumento. Considere 1 dia extra de recuperacao.",
        "alto": "RISCO ALTO de lesao. Reduza volume nesta semana ou faca dia(s) leve(s).",
        "indefinido": "Dados insuficientes (precisa 28 dias de historico).",
    }.get(last["zone"], "")
    return {**last, "recommendation": rec}
