"""HR zones do usuario + classificador de zona por avgHR."""
from __future__ import annotations

import functools

from ..db import connect


@functools.lru_cache(maxsize=1)
def get_default_zones() -> dict | None:
    """Retorna as zonas DEFAULT (cobre todos sports se nao houver especifico)."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM hr_zones
            WHERE sport = 'default'
            ORDER BY rowid LIMIT 1
            """
        ).fetchone()
    if not row:
        # fallback: qualquer zona disponivel
        with connect() as conn:
            row = conn.execute("SELECT * FROM hr_zones LIMIT 1").fetchone()
    return dict(row) if row else None


def zone_for_hr(hr: float) -> int:
    """Retorna 0..5 (0 = abaixo de Z1)."""
    z = get_default_zones()
    if not z:
        # fallback: faixas genericas
        if hr < 120: return 1
        if hr < 140: return 2
        if hr < 160: return 3
        if hr < 175: return 4
        return 5
    if hr < (z.get("z1_floor") or 0): return 0
    if hr < (z.get("z2_floor") or 0): return 1
    if hr < (z.get("z3_floor") or 0): return 2
    if hr < (z.get("z4_floor") or 0): return 3
    if hr < (z.get("z5_floor") or 0): return 4
    return 5


# TRIMP por zona (Banister-style: peso exponencial conforme intensidade)
# Z1=warmup, Z5=anaerobico
ZONE_TRIMP_FACTOR = {0: 0.5, 1: 1.0, 2: 1.5, 3: 2.5, 4: 4.0, 5: 6.0}


def trimp_for_activity(duration_min: float, avg_hr: float | None) -> float:
    """TRIMP simplificado: duracao_min * fator_zona(avgHR)."""
    if not avg_hr or avg_hr <= 0:
        return float(duration_min)  # sem HR: so duracao
    zone = zone_for_hr(float(avg_hr))
    return float(duration_min) * ZONE_TRIMP_FACTOR[zone]
