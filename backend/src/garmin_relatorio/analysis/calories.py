"""Calorias: gasto diário (BMR + ativo), por treino e por modalidade.

Fontes:
- daily_metrics.total_kcal / active_kcal / bmr_kcal: gasto total do dia (Garmin)
- activities.calories: gasto por sessão (já em kcal após fix kJ->kcal pro export)

A função kcal/h por modalidade dá referência pra estimar gasto antes do treino.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from ..db import connect


SPORT_LABEL = {
    "run": "Corrida",
    "bike": "Bike",
    "swim": "Nado",
    "strength": "Força",
    "yoga": "Yoga",
    "walking": "Caminhada",
    "other": "Outro",
}


def calories_dashboard(days: int = 30) -> dict[str, Any]:
    today = date.today()
    cutoff = (today - timedelta(days=days)).isoformat()

    with connect() as conn:
        daily_df = pd.read_sql_query(
            """
            SELECT date, total_kcal, active_kcal, bmr_kcal, steps
            FROM daily_metrics
            WHERE total_kcal IS NOT NULL AND date >= ?
            ORDER BY date
            """,
            conn,
            params=(cutoff,),
        )
        per_sport_df = pd.read_sql_query(
            """
            SELECT sport, calories, duration_s
            FROM activities
            WHERE calories IS NOT NULL AND duration_s > 600
              AND started_at >= ?
            """,
            conn,
            params=(cutoff,),
        )

    daily_series = []
    if not daily_df.empty:
        for row in daily_df.itertuples():
            daily_series.append({
                "date": row.date,
                "total": int(row.total_kcal) if pd.notna(row.total_kcal) else None,
                "active": int(row.active_kcal) if pd.notna(row.active_kcal) else None,
                "bmr": int(row.bmr_kcal) if pd.notna(row.bmr_kcal) else None,
            })

    # Atual = ultimo dia com dado, enriquecido com kcal/h
    current = daily_series[-1] if daily_series else None
    if current:
        # BMR / 24h = kcal/h em repouso
        current["bmr_per_hour"] = (
            round(current["bmr"] / 24) if current.get("bmr") else None
        )
        # Pega duração total de atividades do mesmo dia pra estimar kcal/h efetivo do treino
        with connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(duration_s), 0), COALESCE(SUM(calories), 0)
                FROM activities WHERE started_at LIKE ? AND calories IS NOT NULL
                """,
                (f"{current['date']}%",),
            ).fetchone()
        total_workout_s, total_workout_kcal = row[0], row[1]
        if total_workout_s > 0 and total_workout_kcal > 0:
            current["workout_minutes"] = int(total_workout_s / 60)
            current["workout_kcal"] = int(total_workout_kcal)
            current["workout_per_hour"] = int(total_workout_kcal * 3600 / total_workout_s)
        else:
            current["workout_minutes"] = 0
            current["workout_kcal"] = 0
            current["workout_per_hour"] = None
    # Médias do período
    avg_total = int(daily_df["total_kcal"].mean()) if not daily_df.empty else None
    avg_active = int(daily_df["active_kcal"].mean()) if not daily_df.empty and daily_df["active_kcal"].notna().any() else None
    avg_bmr = int(daily_df["bmr_kcal"].mean()) if not daily_df.empty and daily_df["bmr_kcal"].notna().any() else None

    # Por modalidade: kcal/h ponderado
    by_sport = []
    if not per_sport_df.empty:
        per_sport_df["kcal_per_h"] = per_sport_df["calories"] * 3600.0 / per_sport_df["duration_s"]
        grouped = per_sport_df.groupby("sport").agg(
            sessions=("calories", "count"),
            total_kcal=("calories", "sum"),
            avg_kcal_per_session=("calories", "mean"),
            avg_kcal_per_h=("kcal_per_h", "mean"),
        ).reset_index()
        # Sort: mais utilizado primeiro
        grouped = grouped.sort_values("total_kcal", ascending=False)
        for r in grouped.itertuples():
            by_sport.append({
                "sport": r.sport,
                "label": SPORT_LABEL.get(r.sport, r.sport),
                "sessions": int(r.sessions),
                "total_kcal": int(r.total_kcal),
                "avg_per_session": int(r.avg_kcal_per_session),
                "avg_per_hour": int(r.avg_kcal_per_h),
            })

    # Soma semanal (segunda da semana atual)
    monday = today - timedelta(days=today.weekday())
    week_df = daily_df[daily_df["date"] >= monday.isoformat()] if not daily_df.empty else daily_df
    week_total = int(week_df["total_kcal"].sum()) if not week_df.empty else 0
    week_active = int(week_df["active_kcal"].sum()) if not week_df.empty and week_df["active_kcal"].notna().any() else 0

    # Comparacao BMR Garmin vs formulas + macros sugeridos baseados em peso/altura/idade
    references = _build_references(avg_total, avg_bmr)

    return {
        "available": current is not None,
        "days": days,
        "current": current,
        "average": {
            "total": avg_total,
            "active": avg_active,
            "bmr": avg_bmr,
        },
        "week_total_kcal": week_total,
        "week_active_kcal": week_active,
        "daily_series": daily_series,
        "by_sport": by_sport,
        "references": references,
    }


def _build_references(avg_tdee: int | None, avg_bmr_garmin: int | None) -> dict[str, Any]:
    """Compara BMR Garmin com Mifflin-StJeor e sugere macros baseados em peso/idade/altura.

    Le user_profile + biometrics mais recente. Retorna None silencioso se faltar dado.
    """
    from . import profile as profile_mod

    p = profile_mod.profile_dashboard()
    if not p.get("available") or not p["weight"].get("kg") or not p.get("age") or not p.get("height_cm"):
        return {"available": False}

    weight = float(p["weight"]["kg"])
    height = float(p["height_cm"])
    age = int(p["age"])
    gender = p.get("gender") or "FEMALE"

    # Mifflin-StJeor (gold standard)
    mifflin = 10 * weight + 6.25 * height - 5 * age + (5 if gender == "MALE" else -161)
    # Harris-Benedict
    if gender == "MALE":
        harris = 88.362 + 13.397 * weight + 4.799 * height - 5.677 * age
    else:
        harris = 447.593 + 9.247 * weight + 3.098 * height - 4.330 * age

    bmr_diff = (avg_bmr_garmin - mifflin) if avg_bmr_garmin else None

    # Macros sugeridos baseado em TDEE para manutencao
    # Proteina: 1.6-2.2 g/kg pra atletas (uso 1.8)
    # Gordura: 25% das kcal totais (0.7-1.0 g/kg)
    # Carbo: resto
    protein_g = round(weight * 1.8)
    protein_kcal = protein_g * 4
    macros = None
    if avg_tdee:
        fat_kcal = round(avg_tdee * 0.25)
        fat_g = round(fat_kcal / 9)
        carb_kcal = max(0, avg_tdee - protein_kcal - fat_kcal)
        carb_g = round(carb_kcal / 4)
        macros = {
            "tdee_target": int(avg_tdee),
            "protein_g": protein_g,
            "protein_kcal": protein_kcal,
            "carb_g": carb_g,
            "carb_kcal": carb_kcal,
            "fat_g": fat_g,
            "fat_kcal": fat_kcal,
            "protein_pct": round(protein_kcal / avg_tdee * 100),
            "carb_pct": round(carb_kcal / avg_tdee * 100),
            "fat_pct": round(fat_kcal / avg_tdee * 100),
        }

    return {
        "available": True,
        "bmr_garmin": avg_bmr_garmin,
        "bmr_mifflin": round(mifflin),
        "bmr_harris": round(harris),
        "bmr_diff_garmin_vs_mifflin": round(bmr_diff) if bmr_diff is not None else None,
        "macros": macros,
    }
