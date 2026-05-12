"""Performance Management Chart (CTL/ATL/TSB) — modelo TrainingPeaks.

CTL = Chronic Training Load = média ponderada exponencial 42 dias do TRIMP diário.
      Aproxima 'fitness' acumulada.
ATL = Acute Training Load = média ponderada exponencial 7 dias do TRIMP.
      Aproxima 'fatigue' atual.
TSB = Training Stress Balance = CTL - ATL.
      'Form' (frescor). Positivo = recuperada; negativo = fadigada.

Interpretação clássica:
- TSB > 25:    super fresca, talvez perdendo fitness
- TSB 5-25:    frescor ideal para racing
- TSB -10 a 5: balanço produtivo (CTL ainda crescendo)
- TSB -30 a -10: overload (sustentável por 1-2 semanas)
- TSB < -30:   alto risco — overreaching iminente
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import math
import pandas as pd

from . import acwr
from ..db import connect


def performance_management(days: int = 180) -> dict[str, Any]:
    """Série diária de CTL/ATL/TSB pelos últimos N dias."""
    # Usa TRIMP diário do ACWR series (já calculado)
    raw_series = acwr.acwr_series(days=days + 50)  # buffer pra warmup
    if not raw_series:
        return {"available": False, "days": days, "series": []}

    df = pd.DataFrame(raw_series)
    df["day"] = pd.to_datetime(df["day"]).dt.date
    df = df.sort_values("day").reset_index(drop=True)
    df["load"] = df["load"].astype(float)

    # EMA — usar pandas ewm. spans 7 (ATL) e 42 (CTL).
    df["atl"] = df["load"].ewm(span=7, adjust=False).mean()
    df["ctl"] = df["load"].ewm(span=42, adjust=False).mean()
    df["tsb"] = df["ctl"] - df["atl"]

    cutoff = date.today() - timedelta(days=days)
    df_out = df[df["day"] >= cutoff]

    series = [
        {
            "date": row.day.isoformat(),
            "load": round(float(row.load), 1),
            "ctl": round(float(row.ctl), 1),
            "atl": round(float(row.atl), 1),
            "tsb": round(float(row.tsb), 1),
        }
        for row in df_out.itertuples()
    ]
    if not series:
        return {"available": False, "days": days, "series": []}

    current = series[-1]
    ctl_now = current["ctl"]
    tsb_now = current["tsb"]

    # Delta CTL nas últimas 4 semanas
    if len(series) > 28:
        ctl_4w_ago = series[-29]["ctl"]
        ctl_delta_4w = round(ctl_now - ctl_4w_ago, 1)
    else:
        ctl_delta_4w = None

    if tsb_now > 25:
        zone = "super_fresh"
        zone_label = "Super fresca"
        message = "Risco de perda de fitness. Hora de aumentar carga."
    elif tsb_now > 5:
        zone = "fresh"
        zone_label = "Pronta"
        message = "Frescor ideal — bom pra prova ou esforço alto."
    elif tsb_now > -10:
        zone = "productive"
        zone_label = "Produtiva"
        message = "Balanço produtivo, fitness crescendo. Continue."
    elif tsb_now > -30:
        zone = "overload"
        zone_label = "Sobrecarga"
        message = "Sustentável por 1-2 semanas. Atenta ao corpo."
    else:
        zone = "risk"
        zone_label = "Alto risco"
        message = "Overreaching iminente. Reduza carga já."

    return {
        "available": True,
        "days": days,
        "series": series,
        "current": current,
        "ctl_delta_4w": ctl_delta_4w,
        "zone": zone,
        "zone_label": zone_label,
        "message": message,
    }


# Suprime warning de pandas se houver
math.nan  # noqa: B018
