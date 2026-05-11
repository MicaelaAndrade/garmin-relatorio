"""Detector de overtraining multi-metrica.

Combina 4 sinais (cada um pesa 1 ponto):
1. HRV em queda: ultimos 3 dias < baseline lower (do healthStatusData)
2. RHR em alta: ultimos 3 dias > baseline upper
3. Sleep score baixo: 3+ noites com score < 50
4. Sono curto: 3+ noites com total < 6h

Score 0 = OK, 1 = atenção, 2+ = sinal forte de overtraining.

Importante: isso NAO substitui sintomas subjetivos (cansaço persistente,
queda de motivação, dor crônica). Use como apoio.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from ..db import connect


def _hrv_baseline_status() -> dict | None:
    """Le healthStatusData salvo no raw de daily_metrics pra pegar HRV + baseline."""
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            "SELECT date, raw FROM daily_metrics WHERE date >= ? ORDER BY date DESC LIMIT 14",
            (cutoff,),
        ).fetchall()

    if not rows:
        return None

    # Extrai HRV e baseline do raw -> health.HRV
    hrvs = []
    baseline_lower = baseline_upper = None
    for r in rows:
        raw = json.loads(r["raw"] or "{}")
        # Tentamos pegar do healthStatusData salvo. Se nao tiver baseline, ignora.
        # No nosso ingest_daily_metrics, salvamos {uds, health}; HRV value veio direto pra coluna.
        # Aqui vamos ler do health-related raw que ficou em wellness antes da insercao.
        # Fallback: usa coluna hrv_overnight.
        pass

    # Mais simples: usa coluna hrv_overnight + estima baseline com ultimos 28d
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, hrv_overnight, resting_hr
            FROM daily_metrics
            WHERE hrv_overnight IS NOT NULL
            ORDER BY date DESC LIMIT 28
            """,
            conn,
        )
    if df.empty or len(df) < 7:
        return None

    df = df.iloc[::-1].reset_index(drop=True)  # asc
    last_3 = df.tail(3)["hrv_overnight"]
    baseline = df.head(len(df) - 3)["hrv_overnight"]
    if baseline.empty:
        return None
    bl_mean = float(baseline.mean())
    bl_std = float(baseline.std() or 1.0)
    return {
        "last_3_avg": float(last_3.mean()),
        "baseline_avg": bl_mean,
        "baseline_lower": bl_mean - bl_std,
        "baseline_upper": bl_mean + bl_std,
    }


def _rhr_status() -> dict | None:
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, resting_hr FROM daily_metrics
            WHERE resting_hr IS NOT NULL
            ORDER BY date DESC LIMIT 28
            """,
            conn,
        )
    if df.empty or len(df) < 7:
        return None
    df = df.iloc[::-1].reset_index(drop=True)
    last_3 = df.tail(3)["resting_hr"]
    baseline = df.head(len(df) - 3)["resting_hr"]
    if baseline.empty:
        return None
    return {
        "last_3_avg": float(last_3.mean()),
        "baseline_avg": float(baseline.mean()),
    }


def _sleep_status() -> dict | None:
    with connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT date, total_min, score
            FROM sleep
            ORDER BY date DESC LIMIT 7
            """,
            conn,
        )
    if df.empty:
        return None
    df = df.iloc[::-1].reset_index(drop=True)
    short_nights = int((df["total_min"] < 360).sum())  # < 6h
    low_score_nights = int(((df["score"].notna()) & (df["score"] < 50)).sum())
    return {
        "short_nights_count": short_nights,
        "low_score_count": low_score_nights,
        "avg_total_min": float(df["total_min"].mean()) if df["total_min"].notna().any() else None,
        "avg_score": float(df["score"].mean()) if df["score"].notna().any() else None,
    }


def overtraining_score() -> dict:
    score = 0
    signals: list[dict] = []

    hrv = _hrv_baseline_status()
    if hrv:
        if hrv["last_3_avg"] < hrv["baseline_lower"]:
            score += 1
            signals.append({
                "kind": "hrv_low",
                "msg": f"HRV últimos 3d ({hrv['last_3_avg']:.0f}ms) abaixo do baseline ({hrv['baseline_avg']:.0f}ms)",
                "weight": 1,
            })

    rhr = _rhr_status()
    if rhr and rhr["last_3_avg"] > rhr["baseline_avg"] + 5:
        score += 1
        signals.append({
            "kind": "rhr_high",
            "msg": f"FC repouso últimos 3d ({rhr['last_3_avg']:.0f}bpm) elevada vs baseline ({rhr['baseline_avg']:.0f}bpm)",
            "weight": 1,
        })

    sleep = _sleep_status()
    if sleep:
        if sleep["short_nights_count"] >= 3:
            score += 1
            signals.append({
                "kind": "sleep_short",
                "msg": f"{sleep['short_nights_count']} noites < 6h nas últimas 7",
                "weight": 1,
            })
        if sleep["low_score_count"] >= 3:
            score += 1
            signals.append({
                "kind": "sleep_score_low",
                "msg": f"{sleep['low_score_count']} noites com score < 50 nas últimas 7",
                "weight": 1,
            })

    if score == 0:
        flag = "ok"
        msg = "Recuperação em dia. Pode treinar normalmente."
    elif score == 1:
        flag = "atencao"
        msg = "Um sinal de fadiga. Considere treino mais leve hoje."
    elif score == 2:
        flag = "alerta"
        msg = "Múltiplos sinais. Sugiro 1-2 dias de descanso ativo (caminhada, alongamento)."
    else:
        flag = "vermelho"
        msg = "Forte sinal de overtraining. Descanso completo + revisar carga e sono."

    return {
        "score": score,
        "max_score": 4,
        "flag": flag,
        "message": msg,
        "signals": signals,
        "hrv": hrv,
        "rhr": rhr,
        "sleep": sleep,
    }
