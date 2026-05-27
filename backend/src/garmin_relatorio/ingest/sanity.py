"""Guards de sanidade pra ingestao — evita gravar lixo de sensor.

O altimetro barometrico do relogio falha intermitentemente desde out/2025,
produzindo elevation_gain impossivel (grade absurdo, barometro flat-lined ou
sentinela negativo). Estes guards descartam valores nao-confiaveis na ingestao,
em vez de propagar lixo pro banco. Usado por garmin.py (live) e garmin_export.py.
"""
from __future__ import annotations

from typing import Any

# Atividades pre-glitch nunca passaram de ~40 m/km; 60 separa limpo de lixo.
GRADE_LIMIT_M_PER_KM = 60.0
MAX_RUN_POWER_W = 600.0  # potencia de corrida amadora plausivel; acima = artefato


def sane_elevation_gain(elev_m: float | None, distance_m: float | None, raw: dict[str, Any]) -> float | None:
    """Retorna elev_m se plausivel, senao None.

    Descarta quando: grade > 60 m/km, barometro flat-lined (max==min) ou
    altitude sentinela (<0 em ambos os extremos) — assinaturas de sensor com defeito.
    """
    if elev_m is None:
        return None
    if distance_m and distance_m > 500:
        grade = elev_m / (distance_m / 1000)
        if grade > GRADE_LIMIT_M_PER_KM:
            return None
    mx, mn = raw.get("maxElevation"), raw.get("minElevation")
    if mx is not None and mn is not None:
        if mx == mn and elev_m:  # barometro travado mas reporta ganho → inconsistente
            return None
        if mx < 0 and mn < 0:  # sentinela tipo -500
            return None
    return elev_m


def sane_run_power(value: float | None, avg_power: float | None = None) -> float | None:
    """Retorna potencia de corrida se plausivel, senao None.

    A potencia do Garmin deriva em parte do barometro, entao corrompe junto com a
    elevacao. Descarta valores impossiveis (>600 W) ou normPower muito acima da media.
    """
    if value is None:
        return None
    if value > MAX_RUN_POWER_W:
        return None
    if avg_power and value > avg_power * 1.5:  # normPower nunca fica 50% acima da media
        return None
    return value
