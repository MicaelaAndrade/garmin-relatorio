"""Composicao corporal: peso, gordura %, musculo %, agua, BMR via balanca de
bioimpedancia (Zepp Life / Mi Body Composition Scale 2 etc).

Calcula valores atuais, tendencia 30d, baseline e bandas-alvo por metrica.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from ..db import connect


# Bandas de referencia (mulher 25-35 anos, ACE / NIH / Garmin guidelines)
# Sao referencias — nao prescritivas. A usuaria/profissional saude define o alvo.
BANDS = {
    "fat_pct": [
        # (max_value, label, rating)
        (18.0, "Atleta", "good"),
        (25.0, "Saudável", "good"),
        (32.0, "Aceitável", "warn"),
        (100.0, "Obesidade", "bad"),
    ],
    "muscle_pct": [
        # Maior = melhor; bandas invertidas (min_value, label, rating)
        (40.0, "Abaixo", "warn"),
        (45.0, "Saudável", "good"),
        (55.0, "Atlético", "good"),
        (100.0, "Excepcional", "good"),
    ],
    "visceral_fat": [
        (9.0, "Ótimo", "good"),
        (14.0, "Atenção", "warn"),
        (100.0, "Alto", "bad"),
    ],
    "water_pct": [
        # Mulher saudavel: 45-60%. Atletas tendem ao limite superior.
        (45.0, "Baixo", "warn"),
        (60.0, "Saudável", "good"),
        (100.0, "Alto", "warn"),
    ],
}


def _rate(value: float | None, key: str) -> dict[str, Any] | None:
    if value is None:
        return None
    bands = BANDS.get(key, [])
    if not bands:
        return None
    if key == "muscle_pct":
        # Higher is better — bands listed in ascending min
        prev_min = 0.0
        for min_val, label, rating in bands:
            if value < min_val:
                return {"label": label, "rating": rating}
            prev_min = min_val
        return {"label": bands[-1][1], "rating": bands[-1][2]}
    # Default: lower is better, bands listed in ascending max
    for max_val, label, rating in bands:
        if value < max_val:
            return {"label": label, "rating": rating}
    return {"label": bands[-1][1], "rating": bands[-1][2]}


def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def body_composition_dashboard(days: int = 180) -> dict[str, Any]:
    """Resumo + serie temporal pro card de composicao corporal."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT measured_at, weight_kg, bmi, fat_pct, water_pct,
                   muscle_pct, bone_mass_kg, bmr_kcal, visceral_fat, source
            FROM body_composition
            ORDER BY measured_at
            """
        ).fetchall()

    if not rows:
        return {"available": False, "reason": "Sem medidas de bioimpedância importadas."}

    series: list[dict[str, Any]] = []
    for r in rows:
        ts = r["measured_at"]
        try:
            dt = datetime.fromisoformat(ts)
            d_iso = dt.astimezone(timezone.utc).date().isoformat()
        except (TypeError, ValueError):
            d_iso = ts[:10]
        series.append({
            "date": d_iso,
            "measured_at": ts,
            "weight_kg": r["weight_kg"],
            "bmi": r["bmi"],
            "fat_pct": r["fat_pct"],
            "water_pct": r["water_pct"],
            "muscle_pct": r["muscle_pct"],
            "bone_mass_kg": r["bone_mass_kg"],
            "bmr_kcal": r["bmr_kcal"],
            "visceral_fat": r["visceral_fat"],
            "source": r["source"],
        })

    latest = series[-1]
    first = series[0]

    # Deltas entre ultimas 4 e 4 anteriores (basta ter 8 medidas pra calcular)
    def _delta_block(key: str) -> dict[str, Any] | None:
        if len(series) < 4:
            return None
        last4 = [s[key] for s in series[-4:] if s.get(key) is not None]
        prev = [s[key] for s in series[-8:-4] if s.get(key) is not None]
        cur = _avg(last4)
        prv = _avg(prev) if prev else None
        delta = round(cur - prv, 2) if cur is not None and prv is not None else None
        return {"current": cur, "previous": prv, "delta": delta}

    deltas = {
        key: _delta_block(key)
        for key in ("weight_kg", "fat_pct", "muscle_pct", "water_pct", "bmr_kcal", "visceral_fat")
    }

    # Total delta (primeira medida vs ultima)
    total_delta = {}
    for key in ("weight_kg", "fat_pct", "muscle_pct"):
        if first.get(key) is not None and latest.get(key) is not None:
            total_delta[key] = round(latest[key] - first[key], 2)

    metrics = [
        {
            "key": "weight_kg",
            "label": "Peso",
            "value": latest["weight_kg"],
            "unit": "kg",
            "rating": None,
            "rating_label": None,
            "delta_4w": (deltas["weight_kg"] or {}).get("delta"),
        },
        {
            "key": "fat_pct",
            "label": "Gordura",
            "value": latest["fat_pct"],
            "unit": "%",
            "rating": _rate(latest["fat_pct"], "fat_pct"),
            "delta_4w": (deltas["fat_pct"] or {}).get("delta"),
        },
        {
            "key": "muscle_pct",
            "label": "Músculo",
            "value": latest["muscle_pct"],
            "unit": "%",
            "rating": _rate(latest["muscle_pct"], "muscle_pct"),
            "delta_4w": (deltas["muscle_pct"] or {}).get("delta"),
        },
        {
            "key": "water_pct",
            "label": "Água",
            "value": latest["water_pct"],
            "unit": "%",
            "rating": _rate(latest["water_pct"], "water_pct"),
            "delta_4w": (deltas["water_pct"] or {}).get("delta"),
        },
        {
            "key": "visceral_fat",
            "label": "Gordura visceral",
            "value": latest["visceral_fat"],
            "unit": "",
            "rating": _rate(latest["visceral_fat"], "visceral_fat"),
            "delta_4w": (deltas["visceral_fat"] or {}).get("delta"),
        },
        {
            "key": "bmr_kcal",
            "label": "BMR",
            "value": latest["bmr_kcal"],
            "unit": "kcal",
            "rating": None,
            "delta_4w": (deltas["bmr_kcal"] or {}).get("delta"),
        },
        {
            "key": "bmi",
            "label": "IMC",
            "value": latest["bmi"],
            "unit": "",
            "rating": None,
            "delta_4w": None,
        },
    ]

    # Insights heuristicos
    insights: list[str] = []
    w_delta = total_delta.get("weight_kg")
    f_delta = total_delta.get("fat_pct")
    m_delta = total_delta.get("muscle_pct")

    if w_delta is not None and abs(w_delta) >= 0.5:
        # Composicao mais importante que peso isolado
        if f_delta is not None and m_delta is not None:
            if f_delta < -0.3 and m_delta >= -0.3:
                insights.append(
                    f"Peso {w_delta:+.1f}kg desde {first['date']}, mas gordura caiu {abs(f_delta):.1f}p.p. e músculo manteve — sinal de recomposição corporal."
                )
            elif f_delta > 0.5 and m_delta < -0.3:
                insights.append(
                    f"Peso {w_delta:+.1f}kg com gordura subindo {f_delta:+.1f}p.p. e músculo caindo — revisar dieta/treino."
                )
            elif w_delta > 0 and m_delta > 0.3:
                insights.append(
                    f"Peso +{w_delta:.1f}kg acompanhado de ganho de músculo (+{m_delta:.1f}p.p.) — hipertrofia."
                )

    d4 = deltas.get("weight_kg") or {}
    if d4.get("delta") and abs(d4["delta"]) >= 0.5:
        direction = "subiu" if d4["delta"] > 0 else "caiu"
        insights.append(
            f"Peso {direction} {abs(d4['delta']):.1f}kg nas últimas 4 medidas vs as 4 anteriores."
        )

    # Frequencia de medidas
    if len(series) >= 7:
        recent_dates = sorted({s["date"] for s in series[-7:]})
        if len(recent_dates) >= 5:
            insights.append(
                "Boa consistência: 5+ medidas nos últimos dias — confia mais nas tendências."
            )

    return {
        "available": True,
        "count": len(series),
        "first_date": first["date"],
        "latest_date": latest["date"],
        "latest": latest,
        "first": first,
        "metrics": metrics,
        "deltas_4w": deltas,
        "total_delta": total_delta,
        "series": series,
        "insights": insights,
        "today": date.today().isoformat(),
    }
